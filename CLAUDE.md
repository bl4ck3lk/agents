# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python platform for batch processing large datasets using LLMs. Available as both a CLI tool and a full-featured web application with user authentication, job queuing, and a Next.js frontend.

Supports multiple input formats (CSV, JSON, JSONL, text, SQLite), sequential or async batch processing, and any OpenAI-compatible API.

## Commands

```bash
# Install dependencies (requires Python 3.12+)
uv pip install -e ".[dev]"

# Run tests
pytest

# Run single test
pytest tests/test_engine.py::test_process_sequential -v

# Unit tests only (skip integration/e2e)
pytest tests/ -k "not integration and not e2e"

# Type checking
mypy agents/

# Linting
ruff check agents/

# Process data (CLI)
agents process input.csv output.csv --prompt "Translate '{text}' to Spanish"

# Process with config file
agents process input.csv output.csv --config job.yaml

# Resume interrupted job
agents resume job_20231119_143022

# Start web API
uvicorn agents.api.app:app --reload --port 8002

# Start processing service
uvicorn agents.processing_service.app:app --reload --port 8001
```

## Architecture

### CLI Data Flow

```
Input File -> Adapter.read_units() -> Data Units -> ProcessingEngine -> LLM -> Results -> Adapter.write_results() -> Output File
```

### Web Application Flow

```
Frontend (Next.js :3000) -> FastAPI Web API (:8002) -> PostgreSQL + S3 (MinIO)
                                    |
                            TaskQ Worker (Gleam, polls DB)
                                    |
                         Processing Service (:8001, Python) -> LLM API
```

1. User uploads file -> presigned URL -> direct upload to S3
2. User creates job -> API inserts task into TaskQ `tasks` table
3. TaskQ Worker polls -> claims task -> calls Processing Service `/process` endpoint
4. Processing Service downloads file, processes with LLM, uploads results to S3
5. Job status updated in PostgreSQL -> user sees progress

### Core Components

- **`agents/adapters/`** - Format-specific readers/writers implementing `DataAdapter` ABC from `base.py`. Each adapter provides `read_units()` (yields dicts), `write_results()`, and `get_schema()`. Path traversal protection via `_validate_path()` in `__init__.py`. SQLite adapter validates queries to prevent SQL injection.

- **`agents/core/engine.py`** - `ProcessingEngine` handles sequential or async batch processing. Uses semaphore-controlled concurrency for async mode. Provides sync `process()` (yields iterator) for CLI and async `process_async()` (yields AsyncIterator) for web/FastAPI contexts.

- **`agents/core/llm_client.py`** - `LLMClient` wraps OpenAI SDK with tenacity-based retry logic for rate limits and API errors. Provides both sync `complete()` and async `complete_async()` methods. Configurable request timeout (default 120s).

- **`agents/core/prompt.py`** - `PromptTemplate` renders user prompts with `{field}` placeholders filled from data unit dicts. Includes prompt injection detection and redaction.

- **`agents/core/postprocessor.py`** - `PostProcessor` extracts JSON from markdown-wrapped LLM responses. Handles dicts, arrays, and primitive JSON values.

- **`agents/core/circuit_breaker.py`** - `CircuitBreaker` tracks consecutive failures and trips after threshold. Thread-safe with `threading.Lock`.

- **`agents/api/`** - FastAPI web application. All endpoints require JWT authentication (except `/health`). Rate limiting with optional Redis backend. Routes in `api/routes/` for jobs, files, API keys, usage, and admin.

- **`agents/api/security.py`** - Fernet-based encryption for API keys at rest. API keys in TaskQ payloads are encrypted, not plaintext.

- **`agents/api/auth/`** - JWT authentication via fastapi-users. Config warns if `SECRET_KEY` not set. Includes OAuth support (Google, GitHub).

- **`agents/processing_service/`** - Separate FastAPI app for processing jobs. Called by TaskQ workers. Protected by bearer token auth (`INTERNAL_SERVICE_TOKEN`). Decrypts API keys from encrypted payloads.

- **`agents/db/`** - SQLAlchemy async models and session management. Forward references use quoted strings for models defined later in file.

- **`agents/storage/`** - S3-compatible storage client (MinIO for dev, AWS S3 for prod). Warns if credentials not set.

- **`agents/utils/config.py`** - Pydantic models for YAML config validation (`JobConfig`, `LLMConfig`, `ProcessingConfig`).

- **`agents/utils/progress.py`** - `ProgressTracker` saves checkpoints to `.checkpoints/` directory for job resumption.

- **`agents/utils/config_env.py`** - Environment variable helpers (`get_env_bool`, `get_env_int`, `get_env_list`, `validate_required_env_vars`).

- **`agents/cli.py`** - Click-based CLI with `process` and `resume` commands.

### Processing Modes

- **Sequential**: One request at a time, simple rate limit handling
- **Async**: Concurrent requests with configurable `batch_size` controlling semaphore limit. Use `process_async()` within existing event loops (FastAPI), `process()` from sync code (CLI).

### Key Environment Variables

- `OPENAI_API_KEY` - Required for LLM API calls
- `OPENAI_BASE_URL` - Optional, for OpenAI-compatible APIs (OpenRouter, etc.)
- `DATABASE_URL` - PostgreSQL connection string (required for web app)
- `SECRET_KEY` - JWT signing key (required for production)
- `ENCRYPTION_KEY` - API key encryption key (required for production)
- `INTERNAL_SERVICE_TOKEN` - Bearer token for processing service auth
- `REDIS_URL` - Optional, enables Redis-backed rate limiting
- `STUCK_JOB_TIMEOUT_MINUTES` - Timeout before stuck jobs are auto-failed (default: 30)

### Security Practices

- All API endpoints (except `/health`) require JWT authentication
- Processing service `/process` endpoint requires bearer token auth
- API keys are Fernet-encrypted before storing in TaskQ payloads
- SQL queries in SQLite adapter are validated (SELECT-only, dangerous keywords blocked)
- Column names in SQLite write are validated against injection
- File downloads are scoped to `uploads/{user_id}/`, `results/{user_id}/`, `outputs/{user_id}/`
- Encryption keys are never printed to stdout
- Error messages to clients are sanitized (no stack traces or internal paths)
- Circuit breaker state is thread-safe
- `print()` is replaced with `logging` throughout
