# Agents

LLM batch processing CLI tool for processing large datasets with LLMs. Supports multiple input formats (CSV, JSON, JSONL, text, SQLite), sequential or async batch processing, and any OpenAI-compatible API.

## Installation

```bash
uv pip install -e ".[dev]"
```

## Usage

```bash
agents process input.csv output.csv --prompt "Translate '{text}' to Spanish"
```

### Command Options

```bash
agents process INPUT_FILE OUTPUT_FILE [OPTIONS]

Options:
  --config PATH              Path to config YAML file
  --prompt TEXT              Prompt template with {field} placeholders
  --model TEXT               LLM model to use (default: gpt-4o-mini)
  --api-key TEXT             OpenAI API key (or set OPENAI_API_KEY)
  --base-url TEXT            API base URL for OpenAI-compatible APIs
  --mode [sequential|async]  Processing mode (default: sequential)
  --batch-size INTEGER       Concurrent requests in async mode (default: 10)
  --max-tokens INTEGER       Maximum tokens in LLM response (default: 1500)
  --preview INTEGER          Preview K random samples before processing all
  --checkin-interval INTEGER Pause every N entries to ask user to continue
  --no-post-process          Disable JSON extraction from LLM output
  --no-merge                 Keep parsed JSON in 'parsed' field
  --include-raw              Include raw LLM output in result
```

## Check-in Feature

The check-in feature pauses processing every N entries to let you decide whether to continue or stop for later resumption.

```bash
# Pause every 100 entries to ask
agents process input.csv output.csv --prompt "..." --checkin-interval 100
```

At each check-in, you'll see:

```
[Check-in] Processed 100/5000 entries.
Continue? [y]es / [n]o (pause to resume later) / [a]ll (finish without asking):
```

- **y/yes** - Continue processing, will ask again at next interval
- **n/no** - Pause and save checkpoint for later resumption
- **a/all** - Continue without further check-ins

## Resuming Interrupted Jobs

Jobs can be resumed after interruption (Ctrl+C), errors, or pausing at a check-in.

### Finding Your Job ID

When you pause or interrupt, the CLI shows the resume command:

```
Paused at 200/5000 entries.
To resume later, run: agents resume job_20251126_205528
```

If you missed it, find job IDs from checkpoint files:

```bash
ls .checkpoints/.progress_*.json
# .checkpoints/.progress_job_20251126_205528.json
```

### Resuming

```bash
agents resume job_20251126_205528

# Override check-in interval for the resumed session
agents resume job_20251126_205528 --checkin-interval 50
```

### Where Data is Saved During Processing

While a job runs, data is saved incrementally to `.checkpoints/`:

```
.checkpoints/
├── .progress_job_YYYYMMDD_HHMMSS.json    # Progress info (processed count, total, metadata)
└── .results_job_YYYYMMDD_HHMMSS.jsonl    # Results (one JSON object per line)
```

**View progress while running:**

```bash
# Count processed items
wc -l .checkpoints/.results_job_*.jsonl

# View last few results
tail -5 .checkpoints/.results_job_*.jsonl

# Pretty-print a result
tail -1 .checkpoints/.results_job_*.jsonl | python -m json.tool

# Check progress info
cat .checkpoints/.progress_job_*.json | python -m json.tool
```

The final output file is only written after processing completes successfully.

## Using Config Files

Create a YAML config file for reusable job settings:

```yaml
llm:
  model: gpt-4o-mini
  temperature: 0.7
  max_tokens: 1500

processing:
  mode: async
  batch_size: 20
  checkin_interval: 100  # Optional: pause every 100 entries

prompt: |
  Translate '{text}' to Spanish.
  Return as JSON with keys: translation, confidence
```

```bash
agents process input.csv output.csv --config job.yaml
```

CLI arguments override config values.

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

## Vocabulary Processing Script

The included `process_vocabulary.sh` script processes Chinese vocabulary data:

```bash
# Run with preview (3 random samples first)
./process_vocabulary.sh

# Skip preview and start immediately
./process_vocabulary.sh --skip-preview
./process_vocabulary.sh -s
```

### Script Features

- **Caches flattened input**: Skips flattening if `data/vocabulary_flat.json` exists
- **Timestamped run folders**: Each run saves to `data/runs/run_YYYYMMDD_HHMMSS/`
- **Latest symlink**: `data/runs/latest` points to most recent run
- **Check-in every 100 entries**: Pause to continue, stop, or finish without asking

### Important: Resuming Script Runs

The script creates a new run folder each time. To resume an interrupted run:

```bash
# DON'T run the script again (creates new run)
./process_vocabulary.sh  # Wrong - starts fresh!

# DO use agents resume directly
agents resume job_20251126_205528  # Correct - continues previous run
```

The resumed job writes output to the original run folder saved in the checkpoint.

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

## Environment Variables

- `OPENAI_API_KEY` - Required for LLM API calls
- `OPENAI_BASE_URL` - Optional, for OpenAI-compatible APIs (OpenRouter, etc.)
