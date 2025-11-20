# Agents

LLM batch processing CLI tool.

## Installation

```bash
uv pip install -e ".[dev]"
```

## Usage

```bash
agents process input.csv output.csv --prompt "Translate '{text}' to Spanish"
```

See `docs/plans/2025-11-19-agents-design.md` for full design.

## Examples

### Translation

```bash
agents process words.csv translations.csv --config docs/examples/translation.yaml
```

### Summarization

```bash
agents process articles.txt summaries.txt --config docs/examples/summarization.yaml
```

### Classification

```bash
agents process posts.jsonl categories.jsonl --config docs/examples/classification.yaml
```

## Development

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy agents/

# Linting
ruff check agents/
```
