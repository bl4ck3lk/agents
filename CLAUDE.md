# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python CLI tool for batch processing large datasets using LLMs. Supports multiple input formats (CSV, JSON, JSONL, text, SQLite), sequential or async batch processing, and any OpenAI-compatible API.

## Commands

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run single test
pytest tests/test_engine.py::test_process_sequential -v

# Type checking
mypy agents/

# Linting
ruff check agents/

# Process data
agents process input.csv output.csv --prompt "Translate '{text}' to Spanish"

# Process with config file
agents process input.csv output.csv --config job.yaml

# Resume interrupted job
agents resume job_20231119_143022
```

## Architecture

### Data Flow

```
Input File → Adapter.read_units() → Data Units → ProcessingEngine → LLM → Results → Adapter.write_results() → Output File
```

### Core Components

- **`agents/adapters/`** - Format-specific readers/writers implementing `DataAdapter` ABC from `base.py`. Each adapter provides `read_units()` (yields dicts), `write_results()`, and `get_schema()`.

- **`agents/core/engine.py`** - `ProcessingEngine` handles sequential or async batch processing. Uses semaphore-controlled concurrency for async mode. Yields results as iterator for streaming progress.

- **`agents/core/llm_client.py`** - `LLMClient` wraps OpenAI SDK with tenacity-based retry logic for rate limits and API errors. Provides both sync `complete()` and async `complete_async()` methods.

- **`agents/core/prompt.py`** - `PromptTemplate` renders user prompts with `{field}` placeholders filled from data unit dicts.

- **`agents/core/postprocessor.py`** - `PostProcessor` extracts JSON from markdown-wrapped LLM responses.

- **`agents/utils/config.py`** - Pydantic models for YAML config validation (`JobConfig`, `LLMConfig`, `ProcessingConfig`).

- **`agents/utils/progress.py`** - `ProgressTracker` saves checkpoints to `.checkpoints/` directory for job resumption.

- **`agents/cli.py`** - Click-based CLI with `process` and `resume` commands.

### Processing Modes

- **Sequential**: One request at a time, simple rate limit handling
- **Async**: Concurrent requests with configurable `batch_size` controlling semaphore limit

### Environment Variables

- `OPENAI_API_KEY` - Required for LLM API calls
- `OPENAI_BASE_URL` - Optional, for OpenAI-compatible APIs (OpenRouter, etc.)
