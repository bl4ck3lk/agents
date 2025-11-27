"""CLI interface for agents."""

import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from agents import __version__
from agents.adapters.base import DataAdapter
from agents.adapters.csv_adapter import CSVAdapter
from agents.adapters.json_adapter import JSONAdapter
from agents.adapters.jsonl_adapter import JSONLAdapter
from agents.adapters.sqlite_adapter import SQLiteAdapter
from agents.adapters.text_adapter import TextAdapter
from agents.core.engine import ProcessingEngine, ProcessingMode
from agents.core.llm_client import LLMClient
from agents.core.prompt import PromptTemplate
from agents.utils.config import load_config
from agents.utils.incremental_writer import IncrementalWriter
from agents.utils.progress import ProgressTracker

# Load .env file for environment variables (API keys, etc.)
load_dotenv()


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Agents - LLM batch processing CLI tool."""
    pass


def get_adapter(input_path: str, output_path: str) -> DataAdapter:
    """Get appropriate adapter based on file extension or URI scheme."""
    # Check if it's a SQLite URI
    if input_path.startswith("sqlite://"):
        return SQLiteAdapter(input_path, output_path)

    # Otherwise, detect by file extension
    ext = Path(input_path).suffix.lower()

    if ext == ".csv":
        return CSVAdapter(input_path, output_path)
    elif ext == ".json":
        return JSONAdapter(input_path, output_path)
    elif ext == ".jsonl":
        return JSONLAdapter(input_path, output_path)
    elif ext == ".txt":
        return TextAdapter(input_path, output_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_file", type=click.Path())
@click.option("--config", type=click.Path(exists=True), help="Path to config YAML file")
@click.option("--prompt", help="Prompt template with {field} placeholders")
@click.option("--model", help="LLM model to use")
@click.option("--api-key", envvar="OPENAI_API_KEY", help="OpenAI API key")
@click.option("--base-url", envvar="OPENAI_BASE_URL", help="API base URL (for OpenRouter, etc.)")
@click.option(
    "--mode",
    type=click.Choice(["sequential", "async"]),
    help="Processing mode",
)
@click.option("--batch-size", type=int, help="Batch size for async mode")
@click.option(
    "--no-post-process",
    is_flag=True,
    default=False,
    help="Disable post-processing of LLM output (extract JSON from markdown)",
)
@click.option(
    "--no-merge",
    is_flag=True,
    default=False,
    help="Do not merge parsed JSON fields into root (keep in 'parsed' field)",
)
@click.option(
    "--include-raw",
    is_flag=True,
    default=False,
    help="Include raw LLM output in result",
)
@click.option(
    "--preview",
    type=int,
    default=0,
    help="Preview K random units before processing all",
)
def process(
    input_file: str,
    output_file: str,
    config: str | None,
    prompt: str | None,
    model: str | None,
    api_key: str | None,
    base_url: str | None,
    mode: str | None,
    batch_size: int | None,
    no_post_process: bool,
    no_merge: bool,
    include_raw: bool,
    preview: int,
) -> None:
    """Process INPUT_FILE and save results to OUTPUT_FILE."""
    # Load config if provided
    if config:
        job_config = load_config(config)
        # CLI args override config values
        final_prompt = prompt or job_config.prompt
        final_model = model or job_config.llm.model
        final_api_key = api_key or job_config.llm.api_key or ""
        final_base_url = base_url or job_config.llm.base_url
        final_mode = mode or job_config.processing.mode
        final_batch_size = batch_size or job_config.processing.batch_size
    else:
        # Use CLI args or defaults
        if not prompt:
            click.echo("Error: --prompt required (or use --config)", err=True)
            sys.exit(1)
        final_prompt = prompt
        final_model = model or "gpt-4o-mini"
        final_api_key = api_key or ""
        final_base_url = base_url
        final_mode = mode or "sequential"
        final_batch_size = batch_size or 10

    if not final_api_key:
        click.echo("Error: API key required (set OPENAI_API_KEY or use --api-key)", err=True)
        sys.exit(1)

    try:
        # Initialize components
        adapter = get_adapter(input_file, output_file)
        llm_client = LLMClient(api_key=final_api_key, model=final_model, base_url=final_base_url)
        prompt_template = PromptTemplate(final_prompt)

        processing_mode = (
            ProcessingMode.SEQUENTIAL if final_mode == "sequential" else ProcessingMode.ASYNC
        )
        engine = ProcessingEngine(
            llm_client,
            prompt_template,
            mode=processing_mode,
            batch_size=final_batch_size,
            post_process=not no_post_process,
            merge_results=not no_merge,
            include_raw_result=include_raw,
        )

        # Process data
        click.echo(f"Processing {input_file} -> {output_file}")
        units = list(adapter.read_units())
        total_units = len(units)
        click.echo(f"Found {total_units} units to process")

        # Assign index to each unit for ordering and resume
        for idx, unit in enumerate(units):
            unit["_idx"] = idx

        # Preview mode
        if preview > 0:
            click.echo(f"\nRunning preview on {preview} random units...")
            preview_units = random.sample(units, min(preview, total_units))

            # Create engine for preview (force sequential)
            preview_engine = ProcessingEngine(
                llm_client,
                prompt_template,
                mode=ProcessingMode.SEQUENTIAL,
                post_process=not no_post_process,
                merge_results=not no_merge,
                include_raw_result=include_raw,
            )

            preview_results = list(preview_engine.process(preview_units))

            click.echo("\nPreview Results:")
            for i, result in enumerate(preview_results, 1):
                click.echo(f"\n--- Unit {i} ---")
                click.echo(json.dumps(result, indent=2, ensure_ascii=False))

            if not click.confirm(f"\nProceed with processing all {total_units} units?"):
                click.echo("Aborted.")
                return

        # Initialize progress tracker and incremental writer
        job_id = f"job_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        checkpoint_dir = Path.cwd() / ".checkpoints"
        job_metadata = {
            "input_file": str(input_file),
            "output_file": str(output_file),
            "prompt": final_prompt,
            "model": final_model,
            "mode": final_mode,
            "batch_size": final_batch_size,
            "no_post_process": no_post_process,
            "no_merge": no_merge,
            "include_raw": include_raw,
        }
        tracker = ProgressTracker(
            total=total_units,
            checkpoint_dir=str(checkpoint_dir),
            job_id=job_id,
            checkpoint_interval=100,
            metadata=job_metadata,
        )
        writer = IncrementalWriter(job_id, checkpoint_dir)

        # Process with progress bar and incremental writes
        failed_count = 0
        with Progress(
            TextColumn("[bold blue]Processing:"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("Processing", total=total_units)

            for result in engine.process(units):
                writer.write_result(result)  # Write immediately to survive crashes
                if "error" in result:
                    failed_count += 1
                    tracker.increment_failed()
                tracker.update(1)
                progress.update(task, advance=1)

        # Final checkpoint
        tracker.save_checkpoint()

        # Read all results sorted by _idx and write final output
        all_results = writer.read_all_results()
        # Strip _idx from final output
        for r in all_results:
            r.pop("_idx", None)
        adapter.write_results(all_results)

        click.echo(f"\nSuccessfully processed {len(all_results)} units")
        click.echo(f"Job ID: {job_id}")
        if failed_count > 0:
            click.echo(f"Failed: {failed_count} units", err=True)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("job_id")
@click.option("--api-key", envvar="OPENAI_API_KEY", help="OpenAI API key")
def resume(job_id: str, api_key: str | None) -> None:
    """Resume processing from a checkpoint using JOB_ID."""
    checkpoint_dir = Path.cwd() / ".checkpoints"

    try:
        # Load checkpoint
        click.echo(f"Loading checkpoint for job: {job_id}")
        tracker = ProgressTracker.load_checkpoint(str(checkpoint_dir), job_id)

        # Extract job metadata
        metadata = tracker.metadata
        input_file = metadata["input_file"]
        output_file = metadata["output_file"]
        prompt = metadata["prompt"]
        model = metadata["model"]
        mode = metadata["mode"]
        batch_size = metadata["batch_size"]
        no_post_process = metadata.get("no_post_process", False)
        no_merge = metadata.get("no_merge", False)
        include_raw = metadata.get("include_raw", False)

        # Use API key from checkpoint or CLI
        final_api_key = api_key or metadata.get("api_key")
        if not final_api_key:
            click.echo("Error: API key required (set OPENAI_API_KEY or use --api-key)", err=True)
            sys.exit(1)

        # Initialize incremental writer and get completed indices
        writer = IncrementalWriter(job_id, checkpoint_dir)
        completed_indices = writer.get_completed_indices()

        # Initialize components
        adapter = get_adapter(input_file, output_file)
        llm_client = LLMClient(api_key=final_api_key, model=model)
        prompt_template = PromptTemplate(prompt)

        processing_mode = (
            ProcessingMode.SEQUENTIAL if mode == "sequential" else ProcessingMode.ASYNC
        )
        engine = ProcessingEngine(
            llm_client,
            prompt_template,
            mode=processing_mode,
            batch_size=batch_size,
            post_process=not no_post_process,
            merge_results=not no_merge,
            include_raw_result=include_raw,
        )

        # Load all units, assign indices, and filter to unprocessed
        all_units = list(adapter.read_units())
        for idx, unit in enumerate(all_units):
            unit["_idx"] = idx

        remaining_units = [u for u in all_units if u["_idx"] not in completed_indices]

        click.echo(f"Found {len(completed_indices)} completed, {len(remaining_units)} remaining")

        if not remaining_units:
            click.echo("All units already processed!")
            # Still write final output in case it wasn't written before
            all_results = writer.read_all_results()
            for r in all_results:
                r.pop("_idx", None)
            adapter.write_results(all_results)
            click.echo(f"Final output written to {output_file}")
            return

        # Process remaining units with progress bar
        failed_count = 0
        with Progress(
            TextColumn("[bold blue]Resuming:"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("Processing", total=len(remaining_units))

            for result in engine.process(remaining_units):
                writer.write_result(result)  # Write immediately
                if "error" in result:
                    failed_count += 1
                    tracker.increment_failed()
                tracker.update(1)
                progress.update(task, advance=1)

        # Final checkpoint
        tracker.save_checkpoint()

        # Read all results sorted by _idx and write final output
        all_results = writer.read_all_results()
        for r in all_results:
            r.pop("_idx", None)
        adapter.write_results(all_results)

        click.echo(f"\nSuccessfully processed {len(remaining_units)} additional units")
        click.echo(f"Total processed: {len(all_results)}/{len(all_units)}")
        if failed_count > 0:
            click.echo(f"Failed: {failed_count} units", err=True)

    except FileNotFoundError:
        click.echo(f"Error: Checkpoint not found for job_id: {job_id}", err=True)
        click.echo(f"Looking in: {checkpoint_dir}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
