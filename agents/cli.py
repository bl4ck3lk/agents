"""CLI interface for agents."""

import click

from agents import __version__


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Agents - LLM batch processing CLI tool."""
    pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_file", type=click.Path())
@click.option("--prompt", required=True, help="Prompt template with {field} placeholders")
@click.option("--model", default="gpt-4o-mini", help="LLM model to use")
@click.option("--api-key", envvar="OPENAI_API_KEY", help="OpenAI API key")
def process(
    input_file: str, output_file: str, prompt: str, model: str, api_key: str
) -> None:
    """Process INPUT_FILE and save results to OUTPUT_FILE."""
    click.echo(f"Processing {input_file} -> {output_file}")
    click.echo(f"Model: {model}")
    click.echo(f"Prompt: {prompt}")
    click.echo("Not yet implemented - coming soon!")


if __name__ == "__main__":
    cli()
