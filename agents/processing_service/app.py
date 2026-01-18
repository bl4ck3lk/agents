"""FastAPI application for processing service."""

from fastapi import FastAPI, HTTPException

from agents.processing_service.processor import get_processor
from agents.processing_service.schemas import (
    HealthResponse,
    ProcessRequest,
    ProcessResponse,
)

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
async def process_job(request: ProcessRequest) -> ProcessResponse:
    """Process a batch LLM job.

    This endpoint is called by TaskQ workers to process jobs.
    It downloads the input file from S3, processes each unit through
    the LLM, and uploads results back to S3.
    """
    processor = get_processor()

    try:
        result = await processor.process(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def main() -> None:
    """Entrypoint for console script."""
    import os

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
