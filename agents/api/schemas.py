from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RunMode(str, Enum):
    sequential = "sequential"
    async_mode = "async"


class RunCreateRequest(BaseModel):
    input_file: str
    output_file: str
    prompt: str | None = None
    config_path: str | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    mode: RunMode | None = None
    batch_size: int | None = None
    max_tokens: int | None = None
    include_raw: bool = False
    no_post_process: bool = False
    no_merge: bool = False
    checkin_interval: int | None = None


class RunResumeRequest(BaseModel):
    api_key: str | None = None
    checkin_interval: int | None = None


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"


class RunInfo(BaseModel):
    job_id: str
    status: RunStatus
    input_file: str
    output_file: str
    prompt_preview: str | None = None
    model: str | None = None
    mode: str | None = None
    batch_size: int | None = None
    max_tokens: int | None = None
    include_raw: bool = False
    no_post_process: bool = False
    no_merge: bool = False
    processed: int = 0
    total: int = 0
    failed: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


class RunListResponse(BaseModel):
    runs: list[RunInfo]


class RunDetailResponse(BaseModel):
    run: RunInfo
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResultItem(BaseModel):
    data: dict[str, Any]


class ResultsResponse(BaseModel):
    job_id: str
    offset: int
    limit: int
    total_returned: int
    results: list[dict[str, Any]]


class PromptTestRequest(BaseModel):
    prompt: str
    variables: dict[str, Any] = Field(default_factory=dict)
    model: str | None = None
    api_key: str
    base_url: str | None = None
    max_tokens: int | None = None


class PromptTestResponse(BaseModel):
    output: str


class CompareRequest(BaseModel):
    prompt: str
    sample: dict[str, Any]
    models: list[str]
    api_key: str
    base_url: str | None = None
    max_tokens: int | None = None


class CompareResult(BaseModel):
    model: str
    output: str


class CompareResponse(BaseModel):
    results: list[CompareResult]
