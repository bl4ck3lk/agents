"""CLI interface for agents."""

import sys
from datetime import datetime
from pathlib import Path

import click
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from agents import __version__
from agents.adapters.csv_adapter import CSVAdapter
from agents.adapters.json_adapter import JSONAdapter
from agents.adapters.jsonl_adapter import JSONLAdapter
from agents.adapters.sqlite_adapter import SQLiteAdapter
from agents.adapters.text_adapter import TextAdapter
from agents.core.engine import ProcessingEngine, ProcessingMode
from agents.core.llm_client import LLMClient
from agents.core.prompt import PromptTemplate
from agents.utils.config import load_config
from agents.utils.progress import ProgressTracker


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Agents - LLM batch processing CLI tool."""
    pass


def get_adapter(input_path: str, output_path: str):
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
@click.option(
    "--mode",
    type=click.Choice(["sequential", "async"]),
    help="Processing mode",
)
@click.option("--batch-size", type=int, help="Batch size for async mode")
def process(
    input_file: str,
    output_file: str,
    config: str | None,
    prompt: str | None,
    model: str | None,
    api_key: str | None,
    mode: str | None,
    batch_size: int | None,
) -> None:
    """Process INPUT_FILE and save results to OUTPUT_FILE."""
    # Load config if provided
    if config:
        job_config = load_config(config)
        # CLI args override config values
        final_prompt = prompt or job_config.prompt
        final_model = model or job_config.llm.model
        final_api_key = api_key or job_config.llm.api_key
        final_mode = mode or job_config.processing.mode
        final_batch_size = batch_size or job_config.processing.batch_size
    else:
        # Use CLI args or defaults
        if not prompt:
            click.echo("Error: --prompt required (or use --config)", err=True)
            sys.exit(1)
        final_prompt = prompt
        final_model = model or "gpt-4o-mini"
        final_api_key = api_key
        final_mode = mode or "sequential"
        final_batch_size = batch_size or 10

    if not final_api_key:
        click.echo("Error: API key required (set OPENAI_API_KEY or use --api-key)", err=True)
        sys.exit(1)

    try:
        # Initialize components
        adapter = get_adapter(input_file, output_file)
        llm_client = LLMClient(api_key=final_api_key, model=final_model)
        prompt_template = PromptTemplate(final_prompt)

        processing_mode = (
            ProcessingMode.SEQUENTIAL if final_mode == "sequential" else ProcessingMode.ASYNC
        )
        engine = ProcessingEngine(
            llm_client, prompt_template, mode=processing_mode, batch_size=final_batch_size
        )

        # Process data
        click.echo(f"Processing {input_file} -> {output_file}")
        units = list(adapter.read_units())
        total_units = len(units)
        click.echo(f"Found {total_units} units to process")

        # Initialize progress tracker
        job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        checkpoint_dir = Path.cwd() / ".checkpoints"
        job_metadata = {
            "input_file": str(input_file),
            "output_file": str(output_file),
            "prompt": final_prompt,
            "model": final_model,
            "mode": final_mode,
            "batch_size": final_batch_size,
        }
        tracker = ProgressTracker(
            total=total_units,
            checkpoint_dir=str(checkpoint_dir),
            job_id=job_id,
            checkpoint_interval=100,
            metadata=job_metadata,
        )

        # Process with progress bar
        results = []
        with Progress(
            TextColumn("[bold blue]Processing:"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("Processing", total=total_units)

            for result in engine.process(units):
                results.append(result)
                if "error" in result:
                    tracker.increment_failed()
                tracker.update(1)
                progress.update(task, advance=1)

        # Final checkpoint
        tracker.save_checkpoint()
        adapter.write_results(results)

        click.echo(f"\nSuccessfully processed {len(results)} units")
        click.echo(f"Job ID: {job_id}")
        if tracker.failed > 0:
            click.echo(f"Failed: {tracker.failed} units", err=True)

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

        # Use API key from checkpoint or CLI
        final_api_key = api_key or metadata.get("api_key")
        if not final_api_key:
            click.echo("Error: API key required (set OPENAI_API_KEY or use --api-key)", err=True)
            sys.exit(1)

        # Initialize components
        adapter = get_adapter(input_file, output_file)
        llm_client = LLMClient(api_key=final_api_key, model=model)
        prompt_template = PromptTemplate(prompt)

        processing_mode = ProcessingMode.SEQUENTIAL if mode == "sequential" else ProcessingMode.ASYNC
        engine = ProcessingEngine(llm_client, prompt_template, mode=processing_mode, batch_size=batch_size)

        # Load all units and skip already processed ones
        click.echo(f"Resuming from unit {tracker.processed}/{tracker.total}")
        all_units = list(adapter.read_units())
        remaining_units = all_units[tracker.processed :]

        if not remaining_units:
            click.echo("All units already processed!")
            return

        # Process remaining units with progress bar
        results = []
        with Progress(
            TextColumn("[bold blue]Resuming:"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("Processing", total=len(remaining_units))

            for result in engine.process(remaining_units):
                results.append(result)
                if "error" in result:
                    tracker.increment_failed()
                tracker.update(1)
                progress.update(task, advance=1)

        # Final checkpoint
        tracker.save_checkpoint()

        # Append results to output file
        if results:
            # Read existing results
            existing_results = []
            try:
                output_path = Path(output_file)
                if output_path.exists():
                    temp_adapter = get_adapter(output_file, output_file)
                    existing_results = list(temp_adapter.read_units())
            except Exception:
                pass

            # Combine and write all results
            all_results = existing_results + results
            adapter.write_results(all_results)

        click.echo(f"\nSuccessfully processed {len(results)} additional units")
        click.echo(f"Total processed: {tracker.processed}/{tracker.total}")
        if tracker.failed > 0:
            click.echo(f"Failed: {tracker.failed} units", err=True)

    except FileNotFoundError:
        click.echo(f"Error: Checkpoint not found for job_id: {job_id}", err=True)
        click.echo(f"Looking in: {checkpoint_dir}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
