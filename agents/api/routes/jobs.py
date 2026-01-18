"""Job management routes."""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.api.auth import current_active_user
from agents.api.routes.api_keys import get_decrypted_api_key
from agents.api.security import get_encryption
from agents.db.models import PlatformAPIKey, User, WebJob
from agents.db.session import get_async_session
from agents.processing_service.usage_tracker import get_usage_tracker
from agents.storage import get_storage_client
from agents.taskq import enqueue_task
from agents.utils.config_env import get_env_bool
from agents.utils.model_validation import validate_model


class UsageLimitsExceeded(HTTPException):
    """Exception raised when user exceeds usage limits."""

    def __init__(self, current_usage: Decimal, limit: Decimal):
        detail = f"Monthly usage limit exceeded: ${current_usage:.2f} of ${limit:.2f} used"
        super().__init__(status_code=429, detail=detail)


def check_usage_limits_enabled() -> bool:
    """Check if usage limits feature is enabled."""
    return get_env_bool("USAGE_LIMITS_ENABLED", default=False)


async def get_active_platform_key(
    session: AsyncSession, provider: str = "openrouter"
) -> PlatformAPIKey | None:
    """Get an active platform API key for the given provider."""
    result = await session.execute(
        select(PlatformAPIKey).where(
            PlatformAPIKey.provider == provider,
            PlatformAPIKey.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


def get_user_identifier(request: Request) -> str:
    """Get rate limit key based on authenticated user."""
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.id}"
    return get_remote_address(request)


limiter = Limiter(key_func=get_user_identifier)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class JobConfig(BaseModel):
    """Job configuration options."""

    mode: str = "async"  # 'sequential' or 'async'
    batch_size: int = 10
    max_tokens: int = 1000
    include_raw: bool = False
    no_post_process: bool = False
    no_merge: bool = False
    # Output format: 'enriched' (original + AI fields) or 'separate' (AI results only)
    output_format: str = "enriched"
    # Optional user-defined output schema for structured extraction
    output_schema: dict | None = None
    # Custom system prompt (optional - uses default if not provided)
    system_prompt: str | None = None


class JobCreateRequest(BaseModel):
    """Request to create a new job."""

    input_file_key: str  # S3 key from file upload
    prompt: str
    model: str = "gpt-4o-mini"
    config: JobConfig | None = None
    api_key_id: str | None = None  # Use stored key
    api_key: str | None = None  # Or provide directly (BYOK)
    base_url: str | None = None

    def validate_model_field(self) -> None:
        """Validate that model is allowed."""
        is_valid, error = validate_model(self.model)
        if not is_valid:
            raise ValueError(error)


class JobResponse(BaseModel):
    """Response for a job."""

    id: str
    status: str
    input_file_url: str
    output_file_url: str | None
    prompt: str
    model: str
    config: dict | None
    total_units: int | None
    processed_units: int
    failed_units: int
    created_at: str
    started_at: str | None
    completed_at: str | None
    error_message: str | None = None

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Response for listing jobs."""

    jobs: list[JobResponse]
    total: int
    offset: int
    limit: int


class JobResultItem(BaseModel):
    """A single result item."""

    index: int
    input: dict
    output: Any
    error: str | None = None


class JobResultsResponse(BaseModel):
    """Response for job results."""

    job_id: str
    results: list[dict]
    total: int
    offset: int
    limit: int


def generate_job_id() -> str:
    """Generate a unique job ID."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    unique = str(uuid4())[:8]
    return f"job_{timestamp}_{unique}"


@router.post("", response_model=JobResponse)
@limiter.limit("20/minute")
async def create_job(
    request: Request,
    body: JobCreateRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> JobResponse:
    """Create a new processing job."""
    storage = get_storage_client()

    # Validate model against whitelist
    try:
        body.validate_model_field()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check usage limits if enabled
    if check_usage_limits_enabled():
        # Note: usage_tracker retrieved here for future quota enforcement features
        _usage_tracker = get_usage_tracker()  # noqa: F841 - Intended for future use
        from sqlalchemy import func

        result = await session.execute(
            select(func.coalesce(func.sum(WebJob.cost_usd), 0)).where(
                WebJob.user_id == str(user.id),
                WebJob.created_at >= datetime.utcnow().replace(day=1, hour=0, minute=0, second=0),
            )
        )
        monthly_usage = result.scalar() or Decimal("0")

        if user.monthly_usage_limit_usd:
            if monthly_usage >= user.monthly_usage_limit_usd:
                raise UsageLimitsExceeded(
                    current_usage=monthly_usage,
                    limit=user.monthly_usage_limit_usd,
                )
            logging.info(
                f"User {user.id} usage check: ${monthly_usage:.2f}/${user.monthly_usage_limit_usd:.2f}"
            )

    # Verify file exists
    file_info = await storage.get_file_info(body.input_file_key)
    if not file_info:
        raise HTTPException(status_code=404, detail="Input file not found")

    # Track API key source
    api_key = body.api_key
    base_url = body.base_url
    used_platform_key = False
    provider = "openrouter"  # Default provider

    if not api_key and body.api_key_id:
        # Look up stored key
        from agents.db.models import APIKey

        result = await session.execute(
            select(APIKey).where(
                APIKey.id == body.api_key_id,
                APIKey.user_id == str(user.id),
            )
        )
        stored_key = result.scalar_one_or_none()
        if not stored_key:
            raise HTTPException(status_code=404, detail="API key not found")

        encryption = get_encryption()
        api_key = encryption.decrypt(stored_key.encrypted_key)
        provider = stored_key.provider
    elif not api_key:
        # Try to get default key for model's provider
        api_key = await get_decrypted_api_key(str(user.id), "openrouter", session)
        if not api_key:
            api_key = await get_decrypted_api_key(str(user.id), "openai", session)
            if api_key:
                provider = "openai"

    # Platform key fallback: if user has no key but can use platform key
    if not api_key and user.can_use_platform_key:
        platform_key = await get_active_platform_key(session, provider="openrouter")
        if platform_key:
            encryption = get_encryption()
            api_key = encryption.decrypt(platform_key.encrypted_key)
            base_url = platform_key.base_url
            provider = platform_key.provider
            used_platform_key = True
            # Default base_url for OpenRouter if not set in platform key
            if not base_url and provider == "openrouter":
                base_url = "https://openrouter.ai/api/v1"

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="No API key available. Either provide api_key, api_key_id, store a default key, or request platform key access.",
        )

    # Generate job ID and S3 keys
    job_id = generate_job_id()
    input_file_url = storage.get_s3_url(body.input_file_key)
    results_key = storage.generate_results_key(job_id)
    results_url = storage.get_s3_url(results_key)

    # Create job record
    config_dict = body.config.model_dump() if body.config else {}
    job = WebJob(
        id=job_id,
        user_id=str(user.id),
        input_file_url=input_file_url,
        prompt=body.prompt,
        model=body.model,
        config=config_dict,
        status="pending",
    )

    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Insert task into TaskQ
    task_payload = {
        "web_job_id": job.id,
        "file_url": input_file_url,
        "prompt": body.prompt,
        "model": body.model,
        "config": config_dict,
        "api_key": api_key,
        "results_url": results_url,
        "base_url": base_url,
        # Usage tracking fields
        "user_id": str(user.id),
        "provider": provider,
        "used_platform_key": used_platform_key,
    }

    try:
        taskq_task_id = await enqueue_task(
            session,
            payload=task_payload,
            idempotency_key=job.id,
        )

        # Update job with TaskQ task ID
        job.taskq_task_id = taskq_task_id
        await session.commit()
    except ValueError as e:
        # TaskQ queue not found - log but don't fail job creation
        # Job will remain in "pending" state until TaskQ is set up
        logging.warning(f"TaskQ enqueue failed for job {job.id}: {e}")

    return JobResponse(
        id=job.id,
        status=job.status,
        input_file_url=job.input_file_url,
        output_file_url=job.output_file_url,
        prompt=job.prompt,
        model=job.model,
        config=job.config,
        total_units=job.total_units,
        processed_units=job.processed_units,
        failed_units=job.failed_units,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error_message=job.error_message,
    )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> JobListResponse:
    """List all jobs for the current user."""
    # Build query
    query = select(WebJob).where(WebJob.user_id == str(user.id))

    if status:
        query = query.where(WebJob.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Get paginated results
    query = query.order_by(WebJob.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    jobs = result.scalars().all()

    return JobListResponse(
        jobs=[
            JobResponse(
                id=job.id,
                status=job.status,
                input_file_url=job.input_file_url,
                output_file_url=job.output_file_url,
                prompt=job.prompt,
                model=job.model,
                config=job.config,
                total_units=job.total_units,
                processed_units=job.processed_units,
                failed_units=job.failed_units,
                created_at=job.created_at.isoformat(),
                started_at=job.started_at.isoformat() if job.started_at else None,
                completed_at=job.completed_at.isoformat() if job.completed_at else None,
                error_message=job.error_message,
            )
            for job in jobs
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> JobResponse:
    """Get job details."""
    result = await session.execute(
        select(WebJob).where(WebJob.id == job_id, WebJob.user_id == str(user.id))
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(
        id=job.id,
        status=job.status,
        input_file_url=job.input_file_url,
        output_file_url=job.output_file_url,
        prompt=job.prompt,
        model=job.model,
        config=job.config,
        total_units=job.total_units,
        processed_units=job.processed_units,
        failed_units=job.failed_units,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error_message=job.error_message,
    )


@router.get("/{job_id}/results", response_model=JobResultsResponse)
async def get_job_results(
    job_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> JobResultsResponse:
    """Get paginated results for a job."""
    import json

    # Verify job exists and belongs to user
    result = await session.execute(
        select(WebJob).where(WebJob.id == job_id, WebJob.user_id == str(user.id))
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Read results from S3
    storage = get_storage_client()
    results_key = storage.generate_results_key(job_id)

    try:
        data = await storage.download_file(results_key)
        lines = data.decode().strip().split("\n")

        # Parse all results
        all_results = [json.loads(line) for line in lines if line.strip()]

        # Paginate
        total = len(all_results)
        paginated = all_results[offset : offset + limit]

        return JobResultsResponse(
            job_id=job_id,
            results=paginated,
            total=total,
            offset=offset,
            limit=limit,
        )
    except Exception:
        # No results yet or file doesn't exist
        return JobResultsResponse(
            job_id=job_id,
            results=[],
            total=0,
            offset=offset,
            limit=limit,
        )


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Cancel a running job."""
    result = await session.execute(
        select(WebJob).where(WebJob.id == job_id, WebJob.user_id == str(user.id))
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel job with status: {job.status}")

    job.status = "cancelled"
    job.completed_at = datetime.utcnow()
    await session.commit()

    # TODO: Cancel TaskQ task if running

    return {"success": True, "status": "cancelled"}


class DownloadResponse(BaseModel):
    """Response for download URL."""

    download_url: str
    expires_in: int


@router.get("/{job_id}/download", response_model=DownloadResponse)
async def get_download_url(
    job_id: str,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> DownloadResponse:
    """Get presigned download URL for completed job output."""
    result = await session.execute(
        select(WebJob).where(WebJob.id == job_id, WebJob.user_id == str(user.id))
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job is not completed (status: {job.status})")

    if not job.output_file_url:
        raise HTTPException(status_code=404, detail="No output file available")

    storage = get_storage_client()

    # Parse S3 URL to get key
    _, output_key = storage.parse_s3_url(job.output_file_url)

    # Generate presigned download URL
    download_url = await storage.generate_presigned_download_url(output_key)

    return DownloadResponse(
        download_url=download_url,
        expires_in=900,  # 15 minutes
    )


@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Delete a job and its associated files."""
    result = await session.execute(
        select(WebJob).where(WebJob.id == job_id, WebJob.user_id == str(user.id))
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Delete associated files from S3
    storage = get_storage_client()

    # Delete results file
    try:
        results_key = storage.generate_results_key(job_id)
        await storage.delete_file(results_key)
    except Exception:
        # Best-effort cleanup: failures deleting S3 results should not block job deletion
        logging.exception(
            "Failed to delete results file from storage for job_id=%s, key=%s",
            job_id,
            results_key,
        )

    # Delete output file if exists
    if job.output_file_url:
        try:
            _, output_key = storage.parse_s3_url(job.output_file_url)
            await storage.delete_file(output_key)
        except Exception:
            # Best-effort cleanup: failures deleting S3 output should not block job deletion
            logging.exception(
                "Failed to delete output file from storage for job_id=%s, key=%s",
                job_id,
                output_key,
            )

    # Delete job record
    await session.delete(job)
    await session.commit()

    return {"success": True}
