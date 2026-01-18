"""FastAPI application for agents web API."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from agents.api.auth import auth_backend, fastapi_users
from agents.api.auth.schemas import UserCreate, UserRead, UserUpdate
from agents.api.job_manager import JobManager
from agents.api.routes import api_keys_router, files_router, jobs_router
from agents.api.routes.admin import router as admin_router
from agents.api.routes.usage import router as usage_router
from agents.api.schemas import (
    CompareRequest,
    CompareResponse,
    CompareResult,
    PromptTestRequest,
    PromptTestResponse,
    ResultsResponse,
    RunCreateRequest,
    RunDetailResponse,
    RunListResponse,
    RunResumeRequest,
)

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
    )  # noqa: E402

from agents.api.auth import auth_backend, fastapi_users
from agents.api.auth.schemas import UserCreate, UserRead, UserUpdate
from agents.api.job_manager import JobManager
from agents.api.routes import api_keys_router, files_router, jobs_router
from agents.api.routes.admin import router as admin_router
from agents.api.routes.usage import router as usage_router
from agents.api.schemas import (
    CompareRequest,
    CompareResponse,
    CompareResult,
    PromptTestRequest,
    PromptTestResponse,
    ResultsResponse,
    RunCreateRequest,
    RunDetailResponse,
    RunListResponse,
    RunResumeRequest,
)
from agents.core.llm_client import LLMClient
from agents.core.prompt import PromptTemplate
from agents.storage import get_storage_client
from agents.utils.config import DEFAULT_MAX_TOKENS


def get_user_identifier(request: Request) -> str:
    """Get rate limit key - prefer user ID from auth, fallback to IP."""
    # Check if we have an authenticated user
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.id}"
    # Fallback to IP address
    return get_remote_address(request)


# Initialize rate limiter
limiter = Limiter(key_func=get_user_identifier)


# Rate limit exception handler
def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded"},
    )


# Initialize FastAPI app
app = FastAPI(title="Agents API")

app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup: ensure storage bucket exists
    try:
        storage = get_storage_client()
        await storage.ensure_bucket_exists()
    except Exception as e:
        print(f"Warning: Could not initialize storage: {e}")

    yield

    # Shutdown: cleanup if needed


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

# Legacy job manager for backwards compatibility with existing UI
manager = JobManager()

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


# Legacy routes for backwards compatibility
@app.post("/runs", response_model=RunDetailResponse, tags=["Legacy"])
@limiter.limit("10/minute")
def create_run(request: Request, body: RunCreateRequest) -> Any:
    """Create a run (legacy endpoint)."""
    if not body.api_key:
        raise HTTPException(status_code=400, detail="api_key is required")
    job = manager.start_job(
        input_file=body.input_file,
        output_file=body.output_file,
        prompt=body.prompt,
        config_path=body.config_path,
        model=body.model,
        api_key=body.api_key,
        base_url=body.base_url,
        mode=body.mode.value if body.mode else None,
        batch_size=body.batch_size,
        max_tokens=body.max_tokens,
        include_raw=body.include_raw,
        no_post_process=body.no_post_process,
        no_merge=body.no_merge,
        checkin_interval=body.checkin_interval,
    )  # noqa: E402
    info = manager.get_run(job.job_id)  # noqa: E402
    return RunDetailResponse(run=info, metadata=manager._job_metadata(job))


@app.post("/runs/{job_id}/resume", response_model=RunDetailResponse, tags=["Legacy"])
def resume_run(job_id: str, body: RunResumeRequest) -> Any:
    """Resume a run (legacy endpoint)."""
    if not body.api_key:
        raise HTTPException(status_code=400, detail="api_key is required")
    job = manager.resume_job(job_id, api_key=body.api_key, checkin_interval=body.checkin_interval)
    info = manager.get_run(job.job_id)
    return RunDetailResponse(run=info, metadata=manager._job_metadata(job))


@app.get("/runs", response_model=RunListResponse, tags=["Legacy"])
def list_runs() -> Any:
    """List runs (legacy endpoint)."""
    runs = manager.list_runs()
    return RunListResponse(runs=runs)


@app.get("/runs/{job_id}", response_model=RunDetailResponse, tags=["Legacy"])
def get_run(job_id: str) -> Any:
    """Get run details (legacy endpoint)."""
    try:
        info = manager.get_run(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run not found")
    job = manager.jobs.get(job_id)
    metadata = manager._job_metadata(job) if job else {}
    return RunDetailResponse(run=info, metadata=metadata)


@app.get("/runs/{job_id}/results", response_model=ResultsResponse, tags=["Legacy"])
def get_results(job_id: str, offset: int = 0, limit: int = 50) -> Any:
    """Get run results (legacy endpoint)."""
    try:
        results = manager.get_results_slice(job_id, offset, limit)
    except KeyError:
        raise HTTPException(status_code=404, detail="run not found")
    return ResultsResponse(
        job_id=job_id,
        offset=offset,
        limit=limit,
        total_returned=len(results),
        results=results,
    )


@app.post("/prompt-test", response_model=PromptTestResponse, tags=["Testing"])
@limiter.limit("30/minute")
async def prompt_test(request: Request, body: PromptTestRequest) -> Any:
    """Test a prompt with variables."""
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
async def compare(request: Request, body: CompareRequest) -> Any:
    """Compare multiple models on the same prompt."""
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
