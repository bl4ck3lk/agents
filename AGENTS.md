# AGENTS.md

Guidance for AI coding agents working on this repository.

## Build/Lint/Test Commands

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Run tests
pytest                                    # All tests
pytest tests/test_engine.py::test_name -v  # Single test
pytest tests/ -v --cov=agents --cov-report=html  # With coverage
pytest tests/ -v -m "not integration"    # Unit tests only
pytest tests/ -v -m integration          # Integration tests only

# Code quality
ruff check agents/ tests/                # Lint
ruff check agents/ tests/ --fix          # Auto-fix
ruff format agents/ tests/               # Format
mypy agents/                             # Type check
make check                               # All checks

# Development
make services-up                          # Start postgres, minio, redis
make db-upgrade                           # Run migrations
make api-dev                              # Start API server
make processing-service                   # Start processing service
```

## Code Style Guidelines

### Imports
- Standard library imports first, then third-party, then local
- Use `from collections.abc import Iterator, AsyncIterator` for collections
- Use `from typing import Any` when needed
- Use `|` for unions: `str | None` (not `Optional[str]`)
- Use generic types: `dict[str, Any]`, `list[str]`, `Iterator[dict]`

```python
import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Any

from third_party_lib import Something
from agents.core.engine import ProcessingEngine
```

### Formatting
- Line length: 100 characters
- Double quotes for strings
- Space indentation (2 for inline, 4 for blocks)
- No trailing whitespace
- Two blank lines between top-level definitions

### Type Hints
- Python 3.14 syntax: `str | None`, `dict[str, Any]` (deferred annotations)
- Always annotate function return types: `-> None`, `-> dict[str, Any]`
- Use `Iterator`/`AsyncIterator` for generators instead of `Iterator` from `typing`
- Use `Any` sparingly; prefer specific types where possible

```python
def process_data(
    items: list[dict[str, Any]],
    mode: ProcessingMode = ProcessingMode.SEQUENTIAL,
) -> Iterator[dict[str, Any]]:
    """Process items and yield results."""
    ...
```

### Naming Conventions
- Classes: `PascalCase` (e.g., `ProcessingEngine`, `CSVAdapter`)
- Functions: `snake_case` (e.g., `process_data`, `read_units`)
- Variables: `snake_case` (e.g., `input_path`, `output_file`)
- Constants: `UPPER_CASE` (e.g., `MAX_RETRIES`, `DEFAULT_TIMEOUT`)
- Private members: `_leading_underscore` (e.g., `_circuit_breaker`)
- Test functions: `test_descriptive_name` (e.g., `test_sequential_processing`)

### Error Handling
- Define custom exception classes for domain-specific errors
- Use `raise ... from e` for exception chaining
- Wrap external API errors in domain-specific exceptions
- Return error information in result dicts (e.g., `{"_error": "message"}`)

```python
class FatalLLMError(Exception):
    """Wrapper for fatal LLM errors."""

    def __init__(self, original_error: Exception) -> None:
        self.original_error = original_error
        super().__init__(f"{type(original_error).__name__}: {original_error}")

try:
    result = api_call()
except AuthenticationError as e:
    raise FatalLLMError(e) from e
```

### Docstrings
- Use Google-style docstrings with `Args:`, `Returns:`, `Yields:`, `Raises:`
- Keep docstrings concise and clear
- Use triple quotes for multiline strings

### Testing
- Use `pytest` as test framework
- Fixtures for reusable test setup
- Mock external dependencies with `unittest.mock.Mock`
- Test both happy paths and error cases
- Use descriptive test names

```python
@pytest.fixture
def mock_client() -> Mock:
    """Create mock LLM client."""
    client = Mock(spec=LLMClient)
    client.complete.return_value = "response"
    return client

def test_sequential_processing(mock_client: Mock) -> None:
    """Test that sequential mode processes items one at a time."""
    engine = ProcessingEngine(mock_client, template)
    results = list(engine.process([{"text": "hello"}]))
    assert len(results) == 1
```

### Async Code
- Use `async def` and `await` for async operations
- Use `AsyncMock` for mocking async functions
- Use `asyncio.Semaphore` for concurrency control
- In FastAPI/async contexts, use `engine.process_async()` (not `engine.process()`)
- The sync `process()` method creates its own event loop and cannot nest inside FastAPI's loop

```python
# In async context (FastAPI, processing service):
async for result in engine.process_async(units):
    yield result

# In sync context (CLI):
for result in engine.process(units):
    print(result)
```

### Configuration
- Use Pydantic models for config validation
- Environment variables via `os.getenv()` or pydantic-settings
- Default values in code, override via environment
- Secret keys should never be logged or committed
- Use `logging` module instead of `print()` for all output
- Encrypt sensitive data at rest via `agents/api/security.py`

### Patterns
- ABCs for interfaces (e.g., `class DataAdapter(ABC)`)
- Dataclasses for simple data containers (`@dataclass`)
- Use generators/yield for streaming large datasets
- Circuit breaker pattern for fault tolerance
- Retry logic with exponential backoff (tenacity library)

### File Structure
- `agents/adapters/` - Data format adapters (CSV, JSON, SQLite, etc.) with path traversal and SQL injection protection
- `agents/core/` - Core processing logic (engine, LLM client, circuit breaker, postprocessor)
- `agents/utils/` - Utilities (config, progress tracking, content moderation, model validation, env helpers)
- `agents/api/` - FastAPI web API (all endpoints require JWT auth via `current_active_user`)
- `agents/api/auth/` - Authentication (fastapi-users, JWT, OAuth)
- `agents/api/security.py` - Fernet encryption for API keys
- `agents/api/routes/` - Route handlers (jobs, files, API keys, usage, admin)
- `agents/processing_service/` - Separate FastAPI service for LLM processing (bearer token auth)
- `agents/db/` - SQLAlchemy async models and session management
- `agents/storage/` - S3-compatible storage client
- `agents/taskq/` - TaskQ client for job queuing
- `tests/` - Test files mirroring source structure
- `alembic/` - Database migrations
