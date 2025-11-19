# Agents - LLM Batch Processing Tool

**Date:** 2025-11-19
**Status:** Design Approved

## Overview

A general-purpose Python CLI tool for processing large datasets using LLMs. Supports multiple input formats (CSV, JSON, JSONL, text, SQLite), handles sequential or async batch processing, and works with any OpenAI-compatible API.

## Use Cases

- Translate lists of words/phrases to multiple languages
- Classify or categorize large datasets
- Enrich data with LLM-generated summaries or analysis
- Extract structured information from unstructured text
- Any task requiring consistent LLM processing across many items

## High-Level Architecture

### Core Components

1. **Data Adapters** - Handle reading/writing different formats (CSV, JSON, JSONL, text, SQLite). Each adapter iterates through data "units" (rows, objects, lines, records) and writes results back.

2. **Processing Engine** - Takes data units, sends them to LLM with user's prompt template, collects responses. Supports two modes:
   - **Sequential**: Process one-by-one (simple, respects rate limits)
   - **Async Batch**: Process multiple items concurrently (faster, configurable batch size)

3. **LLM Client** - Wrapper around OpenAI Python SDK. Handles retries, rate limiting, and provider configuration for any OpenAI-compatible API.

4. **Job Manager** - Orchestrates the workflow: load data → process with LLM → save results. Tracks progress, handles interruptions, supports resume.

### Data Flow

```
Input File → Adapter.read() → Data Units → Processing Engine → LLM → Results → Adapter.write() → Output File
```

## Data Adapters & Prompting

### Adapter Interface

Each adapter implements a common interface:

```python
class DataAdapter(ABC):
    def read_units(self) -> Iterator[dict]  # Yields data units as dicts
    def write_results(self, results: List[dict])  # Writes processed results
    def get_schema(self) -> dict  # Returns structure info (columns, fields, etc.)
```

### Format Examples

- **CSV**: Each row is a unit, dict keys are column names
- **JSON**: Each object is a unit (for arrays) or whole file (for single object)
- **JSONL**: Each line is a parsed JSON object
- **Text**: Each line is `{"line_number": N, "content": "..."}`
- **SQLite**: Each row from a query, columns as dict keys

### Prompt Templating

Users provide a prompt template with placeholders:

```
"Translate '{word}' to Spanish, French, and German. Return JSON: {{"es": "...", "fr": "...", "de": "..."}}"
```

The engine fills placeholders from each data unit dict.

### Output Configuration

- **Format**: `json`, `text`, `structured` (parsed JSON)
- **Merge strategy**: append, update original data, replace

## Processing Engine

### Sequential Mode

```python
for unit in adapter.read_units():
    prompt = template.format(**unit)
    response = client.chat.completions.create(...)
    results.append(parse_response(response))
    progress.update()
```

- Simple, predictable
- Respects rate limits naturally
- Easy to debug
- Good for small datasets or strict rate limits

### Async Batch Mode

```python
async def process_batch(units):
    tasks = [process_unit(u) for u in units]
    return await asyncio.gather(*tasks, return_exceptions=True)

for batch in chunked(adapter.read_units(), batch_size):
    results.extend(await process_batch(batch))
```

- Much faster for large datasets
- Configurable concurrency (e.g., 10 requests at once)
- Built-in semaphore to limit concurrent requests
- Handle exceptions per-item (don't fail entire batch)

### Configuration

```yaml
mode: async  # or sequential
batch_size: 10  # for async mode
max_retries: 3
retry_delay: 1.0  # exponential backoff
```

## Error Handling & Resilience

### Retry Strategy

Use exponential backoff with jitter for transient failures (via `tenacity` library):

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def call_llm(prompt):
    return client.chat.completions.create(...)
```

### Error Categories

1. **Retryable** (rate limits, timeouts, 5xx errors)
   - Auto-retry with backoff
   - Log and continue

2. **Fatal** (invalid API key, model not found)
   - Stop immediately, report error

3. **Per-item failures** (malformed response, parsing errors)
   - Log error with item context
   - Save as `{"error": "...", "item": {...}}`
   - Continue processing other items

### Progress & Resume

Save checkpoint file (`.progress.json`) after every N items:

```json
{
  "processed": 1500,
  "total": 10000,
  "failed": 12,
  "checkpoint_file": "results_partial.jsonl"
}
```

On restart, detect checkpoint and offer to resume. Supports interruption (Ctrl+C), crashes, or API failures.

## CLI Interface & Configuration

### Command Structure

```bash
# Basic usage
agents process input.csv output.csv --prompt "Translate '{text}' to Spanish"

# With config file
agents process input.csv output.csv --config job.yaml

# Resume interrupted job
agents resume job_20231119_143022

# SQLite source
agents process "sqlite://data.db?query=SELECT * FROM words" output.jsonl --config job.yaml
```

### Configuration File (job.yaml)

```yaml
# LLM settings
llm:
  provider: openai  # or openai-compatible endpoint
  model: gpt-4o-mini
  base_url: null  # optional for compatible APIs
  api_key: ${OPENAI_API_KEY}  # env var
  temperature: 0.7
  max_tokens: 500

# Processing
processing:
  mode: async  # or sequential
  batch_size: 10
  max_retries: 3

# Prompt template
prompt: |
  Translate the following word to Spanish, French, and German.
  Word: {word}

  Return ONLY valid JSON: {"es": "...", "fr": "...", "de": "..."}

# Output
output:
  format: json  # json, text, structured
  merge_strategy: extend  # extend original data with results
```

### Progress Display

```
Processing: ████████░░ 1,247/10,000 (12.5%) | Rate: 45/min | ETA: 3m 12s
Errors: 3 | Last: Invalid JSON response (item #1,089)
```

## Project Structure

```
agents/
├── agents/
│   ├── __init__.py
│   ├── cli.py                 # Click-based CLI
│   ├── core/
│   │   ├── __init__.py
│   │   ├── engine.py          # ProcessingEngine (sequential/async)
│   │   ├── job.py             # JobManager (orchestration)
│   │   ├── llm_client.py      # OpenAI client wrapper
│   │   └── prompt.py          # Template rendering
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py            # DataAdapter ABC
│   │   ├── csv_adapter.py
│   │   ├── json_adapter.py
│   │   ├── jsonl_adapter.py
│   │   ├── text_adapter.py
│   │   └── sqlite_adapter.py
│   └── utils/
│       ├── __init__.py
│       ├── progress.py        # Progress tracking & checkpoints
│       └── config.py          # Config loading & validation
├── tests/
│   ├── test_adapters.py
│   ├── test_engine.py
│   └── fixtures/
├── docs/
│   ├── plans/                 # Design docs
│   └── examples/              # Example configs
├── pyproject.toml             # uv/pip config
├── README.md
└── .env.example
```

## Dependencies

### Core Dependencies

- `openai` - LLM client (supports OpenAI-compatible APIs)
- `click` - CLI framework
- `pydantic` - Config validation
- `tenacity` - Retry logic with exponential backoff
- `rich` - Progress bars and beautiful terminal output
- `aiosqlite` - Async SQLite support (for async mode)

### Development Tooling

- `uv` - Fast package installer/manager (replaces pip/poetry)
- `ruff` - Linting + formatting (replaces black, isort, flake8)
- `mypy` - Type checking
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting

## Additional Features

### Dry-Run Mode

Process first N items without calling LLM to test templates:

```bash
agents process input.csv output.csv --config job.yaml --dry-run --limit 5
```

### Cost Tracking

Log token usage and estimated cost per run:

```
Run completed: 10,000 items processed
Tokens used: 450,234 (input: 250,123 | output: 200,111)
Estimated cost: $2.25
```

### Output Validation

Optional JSON schema validation for LLM responses to catch malformed outputs early:

```yaml
output:
  format: json
  schema: schemas/translation_schema.json  # JSON Schema file
```

### Logging

Structured logging with different verbosity levels:

```bash
agents process input.csv output.csv --config job.yaml --log-level DEBUG
```

Logs include:
- Request/response details
- Error traces
- Performance metrics
- Token usage per request

### Example Configurations

Include pre-built configs in `docs/examples/`:

- `translation.yaml` - Multi-language translation
- `summarization.yaml` - Text summarization
- `classification.yaml` - Category classification
- `extraction.yaml` - Structured data extraction

## Success Criteria

1. ✅ Supports CSV, JSON, JSONL, text, and SQLite inputs
2. ✅ Works with any OpenAI-compatible API
3. ✅ Sequential and async batch processing modes
4. ✅ Robust error handling with retries and checkpoints
5. ✅ Resume interrupted jobs
6. ✅ Clear progress tracking
7. ✅ Flexible prompt templating
8. ✅ Dry-run mode for testing
9. ✅ Cost tracking
10. ✅ Modern Python tooling (uv, ruff, mypy)

## Future Enhancements

- Streaming responses for real-time output
- Multi-model fallback (try different models if one fails)
- Result caching to avoid re-processing identical inputs
- Web UI for job monitoring
- Webhooks for job completion notifications
