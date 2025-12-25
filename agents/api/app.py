from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from agents.api.job_manager import JobManager
from agents.api.schemas import (
    CompareRequest,
    CompareResponse,
    CompareResult,
    PromptTestRequest,
    PromptTestResponse,
    ResultItem,
    ResultsResponse,
    RunCreateRequest,
    RunDetailResponse,
    RunListResponse,
    RunResumeRequest,
)
from agents.core.llm_client import LLMClient
from agents.core.prompt import PromptTemplate
from agents.utils.config import DEFAULT_MAX_TOKENS

app = FastAPI(title="Agents UI", version="0.1")

# Global job manager
manager = JobManager()

# Mount static assets
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> Any:
    return FileResponse(static_dir / "index.html")


@app.post("/runs", response_model=RunDetailResponse)
def create_run(body: RunCreateRequest) -> Any:
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
    )
    info = manager.get_run(job.job_id)
    return RunDetailResponse(run=info, metadata=manager._job_metadata(job))


@app.post("/runs/{job_id}/resume", response_model=RunDetailResponse)
def resume_run(job_id: str, body: RunResumeRequest) -> Any:
    if not body.api_key:
        raise HTTPException(status_code=400, detail="api_key is required")
    job = manager.resume_job(job_id, api_key=body.api_key, checkin_interval=body.checkin_interval)
    info = manager.get_run(job.job_id)
    return RunDetailResponse(run=info, metadata=manager._job_metadata(job))


@app.get("/runs", response_model=RunListResponse)
def list_runs() -> Any:
    runs = manager.list_runs()
    return RunListResponse(runs=runs)


@app.get("/runs/{job_id}", response_model=RunDetailResponse)
def get_run(job_id: str) -> Any:
    try:
        info = manager.get_run(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run not found")
    # Metadata may be missing for legacy entries
    job = manager.jobs.get(job_id)
    metadata = manager._job_metadata(job) if job else {}
    return RunDetailResponse(run=info, metadata=metadata)


@app.get("/runs/{job_id}/results", response_model=ResultsResponse)
def get_results(job_id: str, offset: int = 0, limit: int = 50) -> Any:
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


@app.post("/prompt-test", response_model=PromptTestResponse)
async def prompt_test(body: PromptTestRequest) -> Any:
    client = LLMClient(
        api_key=body.api_key,
        model=body.model or "gpt-4o-mini",
        base_url=body.base_url,
        max_tokens=body.max_tokens or DEFAULT_MAX_TOKENS,
    )
    prompt = PromptTemplate(body.prompt).render(body.variables)
    output = await client.complete_async(prompt)
    return PromptTestResponse(output=output)


@app.post("/compare", response_model=CompareResponse)
async def compare(body: CompareRequest) -> Any:
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


@app.get("/examples")
def list_examples() -> Any:
    examples_dir = Path(__file__).parent.parent.parent / "docs" / "examples"
    examples: dict[str, str] = {}
    for path in examples_dir.glob("*.yaml"):
        examples[path.name] = path.read_text()
    return examples


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    """Entrypoint for console script."""
    import uvicorn

    uvicorn.run("agents.api.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
