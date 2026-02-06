"""File upload and management routes."""

import os
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from agents.api.auth import current_active_user
from agents.api.utils import parse_file_metadata
from agents.db.models import User
from agents.storage import get_storage_client


def get_user_identifier(request: Request) -> str:
    """Get rate limit key based on authenticated user."""
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.id}"
    return get_remote_address(request)


limiter = Limiter(key_func=get_user_identifier)

router = APIRouter(prefix="/files", tags=["Files"])


class UploadRequest(BaseModel):
    """Request for presigned upload URL."""

    filename: str
    content_type: str = "application/octet-stream"
    size_bytes: int | None = None  # For validation


class UploadResponse(BaseModel):
    """Response with presigned upload URL."""

    file_id: str
    upload_url: str
    fields: dict[str, str]
    key: str
    expires_in: int


class ConfirmUploadRequest(BaseModel):
    """Request to confirm file upload."""

    file_id: str
    key: str


class FileInfoResponse(BaseModel):
    """Response with file information."""

    file_id: str
    key: str
    size: int | None
    content_type: str | None
    download_url: str
    # Metadata fields (populated after confirm)
    row_count: int | None = None
    columns: list[str] | None = None
    preview_rows: list[dict[str, Any]] | None = None
    file_type: str | None = None


# Allowed file extensions
ALLOWED_EXTENSIONS = {".csv", ".json", ".jsonl", ".txt"}
MAX_FILE_SIZE_MB = 100


@router.post("/upload", response_model=UploadResponse)
@limiter.limit("30/minute")
async def request_upload_url(
    request: Request,
    body: UploadRequest,
    user: User = Depends(current_active_user),
) -> UploadResponse:
    """Get a presigned URL for file upload."""
    # Validate file extension
    ext = os.path.splitext(body.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Validate file size if provided
    if body.size_bytes and body.size_bytes > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE_MB}MB",
        )

    storage = get_storage_client()
    file_id = str(uuid4())

    # Generate unique key for this upload
    key = storage.generate_upload_key(str(user.id), body.filename)

    # Get presigned POST data
    presigned = await storage.generate_presigned_upload_url(
        key=key,
        content_type=body.content_type,
        max_size_mb=MAX_FILE_SIZE_MB,
    )

    return UploadResponse(
        file_id=file_id,
        upload_url=presigned["url"],
        fields=presigned["fields"],
        key=key,
        expires_in=presigned["expires_in"],
    )


@router.post("/confirm", response_model=FileInfoResponse)
async def confirm_upload(
    body: ConfirmUploadRequest,
    user: User = Depends(current_active_user),
) -> FileInfoResponse:
    """Confirm file upload and validate the file."""
    storage = get_storage_client()

    # Check if file exists
    file_info = await storage.get_file_info(body.key)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")

    # Verify the key belongs to this user
    if not body.key.startswith(f"uploads/{user.id}/"):
        raise HTTPException(status_code=403, detail="Access denied")

    # Generate download URL
    download_url = await storage.generate_presigned_download_url(body.key)

    # Parse file to extract metadata (columns, row count, preview)
    try:
        metadata = await parse_file_metadata(body.key, storage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse file: {e}",
        ) from e

    return FileInfoResponse(
        file_id=body.file_id,
        key=body.key,
        size=file_info.get("size"),
        content_type=file_info.get("content_type"),
        download_url=download_url,
        row_count=metadata.row_count,
        columns=metadata.columns,
        preview_rows=metadata.preview_rows,
        file_type=metadata.file_type,
    )


@router.get("/{file_id}", response_model=FileInfoResponse)
async def get_file_download_url(
    file_id: str,
    key: str,
    user: User = Depends(current_active_user),
) -> FileInfoResponse:
    """Get a presigned download URL for a file."""
    storage = get_storage_client()

    # Verify the key belongs to this user (uploads, results, or outputs scoped by user)
    user_prefix = f"uploads/{user.id}/"
    results_prefix = f"results/{user.id}/"
    outputs_prefix = f"outputs/{user.id}/"

    if not (
        key.startswith(user_prefix)
        or key.startswith(results_prefix)
        or key.startswith(outputs_prefix)
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if file exists
    file_info = await storage.get_file_info(key)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")

    # Generate download URL
    download_url = await storage.generate_presigned_download_url(key)

    return FileInfoResponse(
        file_id=file_id,
        key=key,
        size=file_info.get("size"),
        content_type=file_info.get("content_type"),
        download_url=download_url,
    )


@router.delete("/{key:path}")
async def delete_file(
    key: str,
    user: User = Depends(current_active_user),
) -> dict:
    """Delete a file."""
    storage = get_storage_client()

    # Verify the key belongs to this user
    if not key.startswith(f"uploads/{user.id}/"):
        raise HTTPException(status_code=403, detail="Access denied")

    await storage.delete_file(key)

    return {"success": True}
