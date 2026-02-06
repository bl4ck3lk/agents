"""Pydantic schemas for processing service."""

from typing import Any

from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    """Request to process a batch job."""

    web_job_id: str = Field(..., description="Job ID from web app")
    file_url: str = Field(..., description="S3 URL of input file")
    prompt: str = Field(..., description="Prompt template with {field} placeholders")
    model: str = Field(..., description="LLM model to use")
    config: dict[str, Any] = Field(default_factory=dict, description="Processing config")
    encrypted_api_key: str = Field(..., description="Fernet-encrypted LLM API key")
    results_url: str = Field(..., description="S3 URL to write results")
    base_url: str | None = Field(None, description="Optional base URL for LLM API")

    # Usage tracking fields (optional - if not provided, usage won't be recorded)
    user_id: str | None = Field(None, description="User ID for usage tracking")
    provider: str = Field("openrouter", description="API provider (openrouter, openai, etc.)")
    used_platform_key: bool = Field(False, description="Whether platform key was used")


class ProcessResponse(BaseModel):
    """Response from processing a batch job."""

    success: bool
    job_id: str
    processed: int = 0
    failed: int = 0
    total: int = 0
    results_url: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str = "0.1.0"
