from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agents.api.schemas import RunInfo, RunStatus
from agents.cli import get_adapter
from agents.core.engine import PARSE_ERROR_KEY, ProcessingEngine, ProcessingMode
from agents.core.llm_client import LLMClient
from agents.core.prompt import PromptTemplate
from agents.utils.config import DEFAULT_MAX_TOKENS, JobConfig, load_config
from agents.utils.incremental_writer import IncrementalWriter
from agents.utils.progress import ProgressTracker


@dataclass
class Job:
    job_id: str
    input_file: str
    output_file: str
    prompt: str
    model: str
    api_key: str
    base_url: str | None
    mode: str
    batch_size: int
    max_tokens: int
    include_raw: bool
    no_post_process: bool
    no_merge: bool
    checkin_interval: int | None
    status: RunStatus = RunStatus.pending
    processed: int = 0
    total: int = 0
    failed: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tracker: ProgressTracker | None = None
    writer: IncrementalWriter | None = None
    thread: threading.Thread | None = None


class JobManager:
    def __init__(self, checkpoint_dir: Path | None = None) -> None:
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self.checkpoint_dir = checkpoint_dir or Path.cwd() / ".checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._load_existing_checkpoints()

    def _load_existing_checkpoints(self) -> None:
        """Discover past runs from checkpoint files so they appear in the UI."""
        for progress_file in self.checkpoint_dir.glob(".progress_*.json"):
            with open(progress_file) as f:
                data = json.load(f)
            job_id = data.get("job_id") or progress_file.stem.replace(".progress_", "")
            # Skip if already registered (API-created job)
            if job_id in self.jobs:
                continue
            metadata = data.get("metadata", {})
            total = data.get("total", 0)
            processed = data.get("processed", 0)
            failed = data.get("failed", 0)
            status = RunStatus.completed if processed >= total and total > 0 else RunStatus.paused
            job = Job(
                job_id=job_id,
                input_file=metadata.get("input_file", ""),
                output_file=metadata.get("output_file", ""),
                prompt=metadata.get("prompt", ""),
                model=metadata.get("model", ""),
                api_key=metadata.get("api_key", ""),
                base_url=metadata.get("base_url"),
                mode=metadata.get("mode", "sequential"),
                batch_size=metadata.get("batch_size", 10),
                max_tokens=metadata.get("max_tokens", DEFAULT_MAX_TOKENS),
                include_raw=metadata.get("include_raw", False),
                no_post_process=metadata.get("no_post_process", False),
                no_merge=metadata.get("no_merge", False),
                checkin_interval=metadata.get("checkin_interval"),
                status=status,
                processed=processed,
                total=total,
                failed=failed,
                started_at=None,
                finished_at=None,
                metadata=metadata,
            )
            self.jobs[job_id] = job

    def _build_job(
        self,
        config: JobConfig,
        api_key: str,
        input_file: str,
        output_file: str,
        prompt_override: str | None = None,
        model_override: str | None = None,
        base_url: str | None = None,
        mode_override: str | None = None,
        batch_size_override: int | None = None,
        max_tokens_override: int | None = None,
        include_raw: bool = False,
        no_post_process: bool = False,
        no_merge: bool = False,
        checkin_interval: int | None = None,
        job_id: str | None = None,
    ) -> Job:
        job_id = job_id or f"job_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        llm = config.llm
        proc = config.processing
        prompt = prompt_override or config.prompt
        model = model_override or llm.model
        mode = mode_override or proc.mode
        batch_size = batch_size_override or proc.batch_size
        max_tokens = max_tokens_override or llm.max_tokens
        checkin_interval = checkin_interval or proc.checkin_interval

        job = Job(
            job_id=job_id,
            input_file=input_file,
            output_file=output_file,
            prompt=prompt,
            model=model,
            api_key=api_key,
            base_url=base_url or llm.base_url,
            mode=mode,
            batch_size=batch_size,
            max_tokens=max_tokens,
            include_raw=include_raw,
            no_post_process=no_post_process,
            no_merge=no_merge,
            checkin_interval=checkin_interval,
            metadata={},
        )
        return job

    def start_job(
        self,
        *,
        input_file: str,
        output_file: str,
        prompt: str | None,
        config_path: str | None,
        model: str | None,
        api_key: str,
        base_url: str | None,
        mode: str | None,
        batch_size: int | None,
        max_tokens: int | None,
        include_raw: bool,
        no_post_process: bool,
        no_merge: bool,
        checkin_interval: int | None,
    ) -> Job:
        """Start a new processing job in the background."""
        if config_path:
            cfg = load_config(config_path)
        else:
            # Build minimal config from provided fields
            cfg = JobConfig(
                llm=config_llm(api_key),
                processing=config_processing(
                    mode or "sequential", batch_size or 10, checkin_interval
                ),
                prompt=prompt or "",
            )
        if not prompt and not cfg.prompt:
            raise ValueError("Prompt is required (or provide config_path)")

        job = self._build_job(
            cfg,
            api_key=api_key,
            input_file=input_file,
            output_file=output_file,
            prompt_override=prompt,
            model_override=model,
            base_url=base_url,
            mode_override=mode,
            batch_size_override=batch_size,
            max_tokens_override=max_tokens,
            include_raw=include_raw,
            no_post_process=no_post_process,
            no_merge=no_merge,
            checkin_interval=checkin_interval,
        )

        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        job.thread = thread
        job.status = RunStatus.running
        with self.lock:
            self.jobs[job.job_id] = job
        thread.start()
        return job

    def resume_job(self, job_id: str, api_key: str | None, checkin_interval: int | None) -> Job:
        tracker = ProgressTracker.load_checkpoint(str(self.checkpoint_dir), job_id)
        metadata = tracker.metadata
        api_key_final = api_key or ""
        if not api_key_final:
            raise ValueError("API key required to resume job")

        cfg = JobConfig(
            llm=config_llm(
                api_key_final,
                model=metadata.get("model"),
                base_url=metadata.get("base_url"),
                max_tokens=metadata.get("max_tokens", DEFAULT_MAX_TOKENS),
            ),
            processing=config_processing(
                metadata.get("mode", "sequential"),
                metadata.get("batch_size", 10),
                checkin_interval or metadata.get("checkin_interval"),
            ),
            prompt=metadata.get("prompt", ""),
        )
        job = self._build_job(
            cfg,
            api_key=api_key_final,
            input_file=metadata["input_file"],
            output_file=metadata["output_file"],
            prompt_override=metadata.get("prompt"),
            model_override=metadata.get("model"),
            base_url=metadata.get("base_url"),
            mode_override=metadata.get("mode"),
            batch_size_override=metadata.get("batch_size"),
            max_tokens_override=metadata.get("max_tokens"),
            include_raw=metadata.get("include_raw", False),
            no_post_process=metadata.get("no_post_process", False),
            no_merge=metadata.get("no_merge", False),
            checkin_interval=checkin_interval or metadata.get("checkin_interval"),
            job_id=job_id,
        )
        job.metadata = metadata
        thread = threading.Thread(
            target=self._resume_job, args=(job, tracker, api_key_final), daemon=True
        )
        job.thread = thread
        job.status = RunStatus.running
        with self.lock:
            self.jobs[job.job_id] = job
        thread.start()
        return job

    def list_runs(self) -> list[RunInfo]:
        with self.lock:
            runs = [self._job_to_info(job) for job in self.jobs.values()]
        # Sort by start/created desc
        return sorted(runs, key=lambda r: r.started_at or "", reverse=True)

    def get_run(self, job_id: str) -> RunInfo:
        with self.lock:
            job = self.jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        return self._job_to_info(job)

    def get_results_slice(self, job_id: str, offset: int, limit: int) -> list[dict[str, Any]]:
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        path = job.writer.path if job.writer else self.checkpoint_dir / f".results_{job_id}.jsonl"
        return read_results_slice(path, offset, limit)

    def _job_to_info(self, job: Job) -> RunInfo:
        return RunInfo(
            job_id=job.job_id,
            status=job.status,
            input_file=job.input_file,
            output_file=job.output_file,
            prompt_preview=job.prompt[:120] + ("..." if len(job.prompt) > 120 else ""),
            model=job.model,
            mode=job.mode,
            batch_size=job.batch_size,
            max_tokens=job.max_tokens,
            include_raw=job.include_raw,
            no_post_process=job.no_post_process,
            no_merge=job.no_merge,
            processed=job.processed,
            total=job.total,
            failed=job.failed,
            started_at=job.started_at.isoformat() if job.started_at else None,
            finished_at=job.finished_at.isoformat() if job.finished_at else None,
            error=job.error,
        )

    def _run_job(self, job: Job) -> None:
        """Internal worker to process a new job."""
        job.started_at = datetime.now(UTC)
        try:
            adapter = get_adapter(job.input_file, job.output_file)
            units = list(adapter.read_units())
            job.total = len(units)
            for idx, unit in enumerate(units):
                unit["_idx"] = idx

            tracker = ProgressTracker(
                total=job.total,
                checkpoint_dir=str(self.checkpoint_dir),
                job_id=job.job_id,
                checkpoint_interval=100,
                metadata=self._job_metadata(job),
            )
            writer = IncrementalWriter(job.job_id, self.checkpoint_dir)
            job.tracker = tracker
            job.writer = writer

            processing_mode = (
                ProcessingMode.SEQUENTIAL if job.mode == "sequential" else ProcessingMode.ASYNC
            )
            engine = ProcessingEngine(
                LLMClient(
                    api_key=job.api_key,
                    model=job.model,
                    base_url=job.base_url,
                    max_tokens=job.max_tokens,
                ),
                PromptTemplate(job.prompt),
                mode=processing_mode,
                batch_size=job.batch_size,
                post_process=not job.no_post_process,
                merge_results=not job.no_merge,
                include_raw_result=job.include_raw,
            )

            error_count = 0
            parse_error_count = 0
            processed_count = 0

            for result in engine.process(units):
                writer.write_result(result)
                if "error" in result:
                    error_count += 1
                    tracker.increment_failed()
                elif PARSE_ERROR_KEY in result:
                    parse_error_count += 1
                    tracker.increment_failed()
                tracker.update(1)
                processed_count += 1
                job.processed = processed_count
                job.failed = tracker.failed

            tracker.save_checkpoint()

            # Write final output
            all_results = writer.read_all_results()
            for r in all_results:
                r.pop("_idx", None)
                r.pop("_retries_exhausted", None)
                r.pop("_attempts", None)
            adapter.write_results(all_results)
            writer.write_failures_file()

            job.status = RunStatus.completed
        except Exception as exc:  # pylint: disable=broad-except
            job.status = RunStatus.failed
            job.error = str(exc)
        finally:
            job.finished_at = datetime.now(UTC)

    def _resume_job(self, job: Job, tracker: ProgressTracker, api_key: str) -> None:
        job.started_at = datetime.now(UTC)
        try:
            metadata = tracker.metadata
            adapter = get_adapter(metadata["input_file"], metadata["output_file"])
            all_units = list(adapter.read_units())
            for idx, unit in enumerate(all_units):
                unit["_idx"] = idx

            writer = IncrementalWriter(job.job_id, self.checkpoint_dir)
            completed_indices = writer.get_completed_indices()
            remaining_units = [u for u in all_units if u["_idx"] not in completed_indices]
            job.total = len(all_units)
            job.processed = len(completed_indices)
            job.failed = tracker.failed

            processing_mode = (
                ProcessingMode.SEQUENTIAL
                if metadata.get("mode") == "sequential"
                else ProcessingMode.ASYNC
            )
            engine = ProcessingEngine(
                LLMClient(
                    api_key=api_key,
                    model=metadata.get("model"),
                    base_url=metadata.get("base_url"),
                    max_tokens=metadata.get("max_tokens", DEFAULT_MAX_TOKENS),
                ),
                PromptTemplate(metadata.get("prompt", "")),
                mode=processing_mode,
                batch_size=metadata.get("batch_size", 10),
                post_process=not metadata.get("no_post_process", False),
                merge_results=not metadata.get("no_merge", False),
                include_raw_result=metadata.get("include_raw", False),
            )

            processed_count = 0
            for result in engine.process(remaining_units):
                writer.write_result(result)
                if "error" in result or PARSE_ERROR_KEY in result:
                    tracker.increment_failed()
                tracker.update(1)
                processed_count += 1
                job.processed = len(completed_indices) + processed_count
                job.failed = tracker.failed

            tracker.save_checkpoint()
            # Write final output
            all_results = writer.read_all_results()
            for r in all_results:
                r.pop("_idx", None)
                r.pop("_retries_exhausted", None)
                r.pop("_attempts", None)
            adapter.write_results(all_results)
            writer.write_failures_file()
            job.status = RunStatus.completed
        except Exception as exc:  # pylint: disable=broad-except
            job.status = RunStatus.failed
            job.error = str(exc)
        finally:
            job.finished_at = datetime.now(UTC)

    def _job_metadata(self, job: Job) -> dict[str, Any]:
        return {
            "input_file": job.input_file,
            "output_file": job.output_file,
            "prompt": job.prompt,
            "model": job.model,
            "base_url": job.base_url,
            "mode": job.mode,
            "batch_size": job.batch_size,
            "max_tokens": job.max_tokens,
            "no_post_process": job.no_post_process,
            "no_merge": job.no_merge,
            "include_raw": job.include_raw,
            "checkin_interval": job.checkin_interval,
        }


def config_llm(
    api_key: str,
    model: str | None = None,
    base_url: str | None = None,
    max_tokens: int | None = None,
):
    from agents.utils.config import LLMConfig

    return LLMConfig(
        api_key=api_key,
        model=model or "gpt-4o-mini",
        base_url=base_url,
        max_tokens=max_tokens or DEFAULT_MAX_TOKENS,
    )


def config_processing(mode: str, batch_size: int, checkin_interval: int | None):
    from agents.utils.config import ProcessingConfig

    return ProcessingConfig(mode=mode, batch_size=batch_size, checkin_interval=checkin_interval)


def read_results_slice(path: Path, offset: int, limit: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not Path(path).exists():
        return results
    start = max(0, offset)
    end = start + limit
    with open(path, encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if idx < start:
                continue
            if idx >= end:
                break
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return results
