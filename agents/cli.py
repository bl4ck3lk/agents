"""CLI interface for agents."""

import sys
from pathlib import Path

import click

from agents import __version__
from agents.adapters.csv_adapter import CSVAdapter
from agents.adapters.jsonl_adapter import JSONLAdapter
from agents.adapters.text_adapter import TextAdapter
from agents.core.engine import ProcessingEngine, ProcessingMode
from agents.core.llm_client import LLMClient
from agents.core.prompt import PromptTemplate
from agents.utils.config import load_config


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Agents - LLM batch processing CLI tool."""
    pass


def get_adapter(input_path: str, output_path: str):
    """Get appropriate adapter based on file extension."""
    ext = Path(input_path).suffix.lower()

    if ext == ".csv":
        return CSVAdapter(input_path, output_path)
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
        click.echo(f"Found {len(units)} units to process")

        results = list(engine.process(units))
        adapter.write_results(results)

        click.echo(f"Successfully processed {len(results)} units")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
