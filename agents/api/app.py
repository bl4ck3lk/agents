"""FastAPI application for agents web API."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import sentry_sdk
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# Initialize Sentry for error monitoring
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("ENVIRONMENT", "development"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        # Don't send PII
        send_default_pii=False,
    )

from agents.api.auth import auth_backend, current_active_user, fastapi_users
from agents.api.auth.schemas import UserCreate, UserRead, UserUpdate
from agents.api.routes import api_keys_router, files_router, jobs_router
from agents.api.routes.admin import router as admin_router
from agents.api.routes.usage import router as usage_router
from agents.api.schemas import (
    CompareRequest,
    CompareResponse,
    CompareResult,
    PromptTestRequest,
    PromptTestResponse,
)
from agents.core.llm_client import LLMClient
from agents.core.prompt import PromptTemplate
from agents.db.models import User
from agents.storage import get_storage_client
from agents.utils.config import DEFAULT_MAX_TOKENS


def get_user_identifier(request: Request) -> str:
    """Get rate limit key - prefer user ID from auth, fallback to IP."""
    # Check if we have an authenticated user
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.id}"
    # Fallback to IP address
    return get_remote_address(request)


# Initialize rate limiter with Redis backend if available, else in-memory fallback
_redis_url = os.getenv("REDIS_URL")
if _redis_url:
    limiter = Limiter(key_func=get_user_identifier, storage_uri=_redis_url)
else:
    limiter = Limiter(key_func=get_user_identifier)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events with graceful shutdown support."""
    import signal

    shutdown_event = asyncio.Event()

    def _signal_handler(signum: int, frame: Any) -> None:
        sig_name = signal.Signals(signum).name
        logger.info("Received %s, initiating graceful shutdown...", sig_name)
        shutdown_event.set()

    # Register signal handlers for graceful shutdown
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _signal_handler)

    # Startup: validate critical env vars in production
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        from agents.utils.config_env import validate_required_env_vars

        try:
            validate_required_env_vars("SECRET_KEY", "ENCRYPTION_KEY", "DATABASE_URL")
        except ValueError as e:
            logger.error("Environment validation failed: %s", e)

    # Startup: ensure storage bucket exists
    try:
        storage = get_storage_client()
        await storage.ensure_bucket_exists()
    except Exception as e:
        logger.warning("Could not initialize storage: %s", e)

    # Start background task to recover stuck jobs
    async def recover_stuck_jobs() -> None:
        """Periodically check for jobs stuck in 'processing' state and re-queue them."""
        from datetime import datetime, timedelta

        from sqlalchemy import select, update

        from agents.db.models import WebJob
        from agents.db.session import async_session_maker

        stuck_timeout = timedelta(minutes=int(os.getenv("STUCK_JOB_TIMEOUT_MINUTES", "30")))

        while not shutdown_event.is_set():
            try:
                await asyncio.sleep(60)  # Check every minute
                async with async_session_maker() as session:
                    cutoff = datetime.utcnow() - stuck_timeout
                    result = await session.execute(
                        select(WebJob).where(
                            WebJob.status == "processing",
                            WebJob.started_at < cutoff,
                        )
                    )
                    stuck_jobs = result.scalars().all()
                    for job in stuck_jobs:
                        logger.warning(
                            "Job %s stuck in processing since %s, marking as failed",
                            job.id,
                            job.started_at,
                        )
                        await session.execute(
                            update(WebJob)
                            .where(WebJob.id == job.id)
                            .values(
                                status="failed",
                                error_message="Job timed out (stuck in processing state)",
                                completed_at=datetime.utcnow(),
                            )
                        )
                    if stuck_jobs:
                        await session.commit()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in stuck job recovery task")

    recovery_task = asyncio.create_task(recover_stuck_jobs())

    yield

    # Shutdown: graceful cleanup
    logger.info("Application shutting down, draining in-flight requests...")
    shutdown_event.set()
    recovery_task.cancel()
    try:
        await recovery_task
    except asyncio.CancelledError:
        pass  # Expected: we just cancelled this task during shutdown


API_DESCRIPTION = """
## Agents LLM Batch Processing API

Process large datasets through LLMs with support for:
- **Multiple LLM Providers**: OpenAI, Anthropic, and OpenRouter
- **Batch Processing**: Concurrent processing with configurable batch sizes
- **File Formats**: CSV, JSON, JSONL support
- **Real-time Progress**: Track job progress and stream results
- **Secure API Key Storage**: Encrypted storage for your LLM API keys

### Authentication

All endpoints (except health check) require JWT authentication.
Obtain a token via `POST /auth/jwt/login` with your email and password.

Include the token in requests as:
```
Authorization: Bearer <token>
```

### Rate Limits

The following rate limits apply per user:
- **Job creation**: 20 requests/minute
- **File uploads**: 30 requests/minute
- **Prompt testing**: 30 requests/minute
- **Model comparison**: 10 requests/minute

### Getting Started

1. Register an account: `POST /auth/register`
2. Login to get a token: `POST /auth/jwt/login`
3. Add an API key: `POST /api-keys`
4. Upload a file: `POST /files/upload` then upload to the presigned URL
5. Create a job: `POST /jobs`
6. Monitor progress: `GET /jobs/{id}`
7. Download results: `GET /jobs/{id}/results`
"""

app = FastAPI(
    title="Agents API",
    description=API_DESCRIPTION,
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Auth", "description": "User authentication and registration"},
        {"name": "Users", "description": "User profile management"},
        {"name": "API Keys", "description": "Manage stored LLM API keys"},
        {"name": "Files", "description": "File upload and management"},
        {"name": "Jobs", "description": "Batch processing job management"},
        {"name": "Testing", "description": "Prompt testing and model comparison"},
        {"name": "Legacy", "description": "Legacy endpoints for backward compatibility"},
        {"name": "Health", "description": "Health check endpoint"},
    ],
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware - restrict to specific methods and headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Requested-With",
        "X-CSRF-Token",
    ],
)

# Include authentication routes
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["Auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["Auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["Auth"],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["Auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["Users"],
)

# Include API routes
app.include_router(api_keys_router)
app.include_router(files_router)
app.include_router(jobs_router)
app.include_router(admin_router)
app.include_router(usage_router)

# Mount static assets for legacy UI
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> Any:
    """Serve legacy UI."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>Agents API</h1><p>API is running. See /docs for documentation.</p>")


# Legacy /runs endpoints have been removed (security: unauthenticated access).
# Use the authenticated /jobs endpoints instead.


@app.post("/prompt-test", response_model=PromptTestResponse, tags=["Testing"])
@limiter.limit("30/minute")
async def prompt_test(
    request: Request,
    body: PromptTestRequest,
    user: User = Depends(current_active_user),
) -> Any:
    """Test a prompt with variables. Requires authentication."""
    client = LLMClient(
        api_key=body.api_key,
        model=body.model or "gpt-4o-mini",
        base_url=body.base_url,
        max_tokens=body.max_tokens or DEFAULT_MAX_TOKENS,
    )
    prompt = PromptTemplate(body.prompt).render(body.variables)
    output = await client.complete_async(prompt)
    return PromptTestResponse(output=output)


@app.post("/compare", response_model=CompareResponse, tags=["Testing"])
@limiter.limit("10/minute")
async def compare(
    request: Request,
    body: CompareRequest,
    user: User = Depends(current_active_user),
) -> Any:
    """Compare multiple models on the same prompt. Requires authentication."""
    results: list[CompareResult] = []
    for model in body.models:
        client = LLMClient(
            api_key=body.api_key,
            model=model,
            base_url=body.base_url,
            max_tokens=body.max_tokens or DEFAULT_MAX_TOKENS,
        )
        prompt = PromptTemplate(body.prompt).render(body.sample)
        output = await client.complete_async(prompt)
        results.append(CompareResult(model=model, output=output))
    return CompareResponse(results=results)


@app.get("/examples", tags=["Examples"])
def list_examples() -> Any:
    """List example configurations."""
    examples_dir = Path(__file__).parent.parent.parent / "docs" / "examples"
    examples: dict[str, str] = {}
    if examples_dir.exists():
        for path in examples_dir.glob("*.yaml"):
            examples[path.name] = path.read_text()
    return examples


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": "0.2.0"}


def main() -> None:
    """Entrypoint for console script."""
    import uvicorn

    uvicorn.run(
        "agents.api.app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )


if __name__ == "__main__":
    main()
