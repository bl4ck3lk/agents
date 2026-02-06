"""Core processing logic for batch jobs."""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from agents.adapters import get_adapter
from agents.api.security import get_encryption
from agents.core.engine import ProcessingEngine, ProcessingMode
from agents.core.llm_client import LLMClient
from agents.core.prompt import PromptTemplate
from agents.processing_service.db_helpers import (
    update_job_progress,
    update_job_status,
)
from agents.processing_service.schemas import ProcessRequest, ProcessResponse
from agents.processing_service.usage_tracker import get_usage_tracker
from agents.storage.client import get_storage_client
from agents.utils.config import DEFAULT_MAX_TOKENS
from agents.utils.config_env import get_env_bool

logger = logging.getLogger(__name__)

# Update progress every N items
PROGRESS_UPDATE_INTERVAL = 10

# Content moderation enabled?
MODERATION_ENABLED = get_env_bool("ENABLE_CONTENT_MODERATION", default=True)


def format_result(
    result: dict[str, Any],
    original_unit: dict[str, Any],
    output_format: str,
    output_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Format a result based on output_format setting.

    Args:
        result: The raw result from processing engine
        original_unit: The original input data unit
        output_format: 'enriched' (original + AI) or 'separate' (AI only)
        output_schema: Optional schema to filter output fields

    Returns:
        Formatted result dict
    """
    if output_format == "separate":
        # Extract just the AI output fields (non-internal fields)
        ai_output = {
            k: v for k, v in result.items() if not k.startswith("_") and k not in original_unit
        }
        # Also include parsed JSON if present
        if "parsed" in result:
            ai_output["parsed"] = result["parsed"]
        # Include index for reference
        if "_idx" in result:
            ai_output["_idx"] = result["_idx"]
        # Include error if present
        if "_error" in result:
            ai_output["_error"] = result["_error"]

        # Filter by output_schema if provided
        if output_schema:
            filtered = {"_idx": ai_output.get("_idx")}
            for key in output_schema:
                if key in ai_output:
                    filtered[key] = ai_output[key]
            if "_error" in ai_output:
                filtered["_error"] = ai_output["_error"]
            return filtered
        return ai_output
    else:
        # enriched mode: return full merged result (default engine behavior)
        if output_schema:
            # Include original fields + specified AI fields
            filtered = {k: v for k, v in result.items() if k.startswith("_")}
            filtered.update(original_unit)
            for key in output_schema:
                if key in result:
                    filtered[key] = result[key]
            return filtered
        return result


class BatchProcessor:
    """Processes batch LLM jobs."""

    def __init__(self) -> None:
        self.storage = get_storage_client()

    async def process(self, request: ProcessRequest) -> ProcessResponse:
        """Process a batch job and return results."""
        temp_dir = None
        try:
            # Update job status to processing
            await update_job_status(request.web_job_id, "processing")

            # Create temp directory for working files
            temp_dir = tempfile.mkdtemp(prefix=f"job_{request.web_job_id}_")
            input_path = Path(temp_dir) / "input"
            results_path = Path(temp_dir) / "results.jsonl"

            # Download input file from S3
            _, key = self.storage.parse_s3_url(request.file_url)
            self.storage.download_file_sync(key, str(input_path))

            # Determine file extension from key
            ext = os.path.splitext(key)[1]
            if ext:
                actual_input = input_path.with_suffix(ext)
                input_path.rename(actual_input)
                input_path = actual_input

            # Get adapter for file type
            adapter = get_adapter(str(input_path))
            units = list(adapter.read_units())

            if not units:
                return ProcessResponse(
                    success=True,
                    job_id=request.web_job_id,
                    processed=0,
                    failed=0,
                    total=0,
                    error="No data units found in input file",
                )

            # Add index to each unit
            for idx, unit in enumerate(units):
                unit["_idx"] = idx

            total = len(units)

            # Decrypt the API key from the encrypted payload
            encryption = get_encryption()
            api_key = encryption.decrypt(request.encrypted_api_key)

            # Auto-detect OpenRouter keys and set base_url
            base_url = request.base_url
            if not base_url and api_key.startswith("sk-or-"):
                base_url = "https://openrouter.ai/api/v1"

            # Create LLM client with optional custom system prompt
            llm_client = LLMClient(
                api_key=api_key,
                model=request.model,
                base_url=base_url,
                max_tokens=request.config.get("max_tokens", DEFAULT_MAX_TOKENS),
                system_prompt=request.config.get("system_prompt"),
            )

            # Create prompt template
            prompt_template = PromptTemplate(request.prompt)

            # Create processing engine
            # Use the configured mode - process_async() works within existing event loops
            config_mode = request.config.get("mode", "async")
            mode = ProcessingMode.SEQUENTIAL if config_mode == "sequential" else ProcessingMode.ASYNC
            engine = ProcessingEngine(
                llm_client=llm_client,
                prompt_template=prompt_template,
                mode=mode,
                batch_size=request.config.get("batch_size", 10),
                post_process=not request.config.get("no_post_process", False),
                include_raw_result=request.config.get("include_raw", False),
                merge_results=not request.config.get("no_merge", False),
            )

            # Get output format settings
            output_format = request.config.get("output_format", "enriched")
            output_schema = request.config.get("output_schema")

            # Build index to original unit mapping for format_result
            units_by_idx = {u.get("_idx", i): u for i, u in enumerate(units)}

            # Process all units
            processed = 0
            failed = 0
            items_since_update = 0
            total_tokens_input = 0
            total_tokens_output = 0

            # Set initial total count
            await update_job_progress(request.web_job_id, 0, 0, total)

            with open(results_path, "w") as f:
                async for result in engine.process_async(units):
                    # Get original unit for this result
                    idx = result.get("_idx", 0)
                    original_unit = units_by_idx.get(idx, {})

                    # Aggregate token usage
                    usage = result.get("_usage", {})
                    total_tokens_input += usage.get("input", 0)
                    total_tokens_output += usage.get("output", 0)

                    # Format result based on output_format
                    formatted = format_result(result, original_unit, output_format, output_schema)

                    # Write result to JSONL
                    f.write(json.dumps(formatted) + "\n")

                    if result.get("_error"):
                        failed += 1
                    else:
                        processed += 1

                    # Periodically update progress in database
                    items_since_update += 1
                    if items_since_update >= PROGRESS_UPDATE_INTERVAL:
                        await update_job_progress(request.web_job_id, processed, failed, total)
                        items_since_update = 0

            # Record usage (only if user_id is provided)
            if request.user_id and (total_tokens_input > 0 or total_tokens_output > 0):
                usage_tracker = get_usage_tracker()
                await usage_tracker.record_usage(
                    job_id=request.web_job_id,
                    user_id=request.user_id,
                    model=request.model,
                    provider=request.provider,
                    tokens_input=total_tokens_input,
                    tokens_output=total_tokens_output,
                    used_platform_key=request.used_platform_key,
                )

            # Upload results to S3
            _, results_key = self.storage.parse_s3_url(request.results_url)
            with open(results_path, "rb") as f:
                await self.storage.upload_file(results_key, f, content_type="application/x-ndjson")

            # Update final job status
            await update_job_status(
                request.web_job_id,
                "completed",
                processed=processed,
                failed=failed,
                total=total,
                output_url=request.results_url,
            )

            return ProcessResponse(
                success=True,
                job_id=request.web_job_id,
                processed=processed,
                failed=failed,
                total=total,
                results_url=request.results_url,
            )

        except Exception as e:
            # Log the full error for debugging (logger.exception includes traceback)
            # Sanitize job_id to prevent log injection (newlines, control chars)
            safe_job_id = request.web_job_id.replace("\n", "").replace("\r", "")[:100]
            logger.exception("Job %s failed", safe_job_id)

            # Extract meaningful error message
            from agents.core.circuit_breaker import CircuitBreakerTripped

            if isinstance(e, CircuitBreakerTripped) and e.status.get("last_error_message"):
                # Use the underlying error, not just "circuit breaker tripped"
                error_message = f"Processing failed: {e.status['last_error_message']}"
            else:
                # Sanitize error message to avoid exposing internal paths/stack traces
                error_message = f"Processing failed: {type(e).__name__}"

            # Update job status to failed
            await update_job_status(
                request.web_job_id,
                "failed",
                error=error_message,
            )

            return ProcessResponse(
                success=False,
                job_id=request.web_job_id,
                error=error_message,
            )

        finally:
            # Cleanup temp directory
            if temp_dir and os.path.exists(temp_dir):
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)


# Global processor instance
_processor: BatchProcessor | None = None


def get_processor() -> BatchProcessor:
    """Get or create processor singleton."""
    global _processor
    if _processor is None:
        _processor = BatchProcessor()
    return _processor
