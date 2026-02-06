"""FastAPI application for processing service."""

import logging
import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agents.processing_service.processor import get_processor
from agents.processing_service.schemas import (
    HealthResponse,
    ProcessRequest,
    ProcessResponse,
)

logger = logging.getLogger(__name__)

# Internal service authentication via shared secret
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "")
security = HTTPBearer()


def verify_internal_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Verify the internal service bearer token."""
    if not INTERNAL_SERVICE_TOKEN:
        logger.warning(
            "INTERNAL_SERVICE_TOKEN not set - processing service is unprotected. "
            "Set INTERNAL_SERVICE_TOKEN env var for production."
        )
        return credentials.credentials
    if credentials.credentials != INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid service token")
    return credentials.credentials


app = FastAPI(
    title="Agents Processing Service",
    description="Internal service for processing LLM batch jobs",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy")


@app.post("/process", response_model=ProcessResponse)
async def process_job(
    request: ProcessRequest,
    _token: str = Depends(verify_internal_token),
) -> ProcessResponse:
    """Process a batch LLM job.

    This endpoint is called by TaskQ workers to process jobs.
    It downloads the input file from S3, processes each unit through
    the LLM, and uploads results back to S3.

    Requires a valid internal service bearer token.
    """
    processor = get_processor()

    try:
        result = await processor.process(request)
        return result
    except Exception as e:
        logger.exception("Processing job failed")
        raise HTTPException(status_code=500, detail="Internal processing error") from e


def main() -> None:
    """Entrypoint for console script."""
    import uvicorn

    reload = os.environ.get("RELOAD", "").lower() in ("true", "1", "yes")
    uvicorn.run(
        "agents.processing_service.app:app",
        host="0.0.0.0",
        port=8001,
        reload=reload,
    )


if __name__ == "__main__":
    main()
