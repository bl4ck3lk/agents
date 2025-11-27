# Circuit Breaker & Enhanced Retry Design

## Overview

Add fault tolerance features to prevent cascading failures and improve retry behavior:
1. **Circuit breaker** - Pause after K consecutive fatal errors, prompt user
2. **Error classification** - Distinguish retryable vs fatal errors
3. **Enhanced retry with jitter** - Prevent thundering herd
4. **Retry failures on resume** - Re-process failed items via `--retry-failures` flag

## Error Classification

### Fatal Errors (count toward circuit breaker)
```python
from openai import AuthenticationError, PermissionDeniedError, BadRequestError

FATAL_ERRORS = (AuthenticationError, PermissionDeniedError, BadRequestError)
```
These indicate configuration problems that won't resolve with retries.

### Retryable Errors (retry with backoff)
```python
from openai import RateLimitError, APITimeoutError, APIError

RETRYABLE_ERRORS = (RateLimitError, APITimeoutError, APIError)
```
These are transient and may succeed on retry.

## Circuit Breaker

### State Tracking
```python
@dataclass
class CircuitBreakerState:
    consecutive_failures: int = 0
    last_error: Exception | None = None
    last_failed_unit: dict | None = None
    
    def record_failure(self, error: Exception, unit: dict) -> None:
        self.consecutive_failures += 1
        self.last_error = error
        self.last_failed_unit = unit
    
    def reset(self) -> None:
        self.consecutive_failures = 0
        self.last_error = None
        self.last_failed_unit = None
    
    def is_tripped(self, threshold: int) -> bool:
        return self.consecutive_failures >= threshold
```

### Trigger Behavior
When `consecutive_failures >= circuit_breaker_threshold`:
1. Pause processing
2. Display error summary
3. Prompt user: `[C]ontinue / [A]bort / [I]nspect`

### User Prompt
```
⚠️  Circuit breaker triggered: 5 consecutive failures

Last error: PermissionDeniedError
Message: You don't have access to this model
Failed unit: {"id": "hsk3_152", "simplified": "辆", ...}

Processed: 438/5000 | Failed: 5 | Success rate: 98.9%

[C]ontinue  [A]bort  [I]nspect details
> 
```

### User Options
- **Continue**: Reset counter, resume processing
- **Abort**: Save checkpoint, write failures file, exit gracefully
- **Inspect**: Show full stack trace, then re-prompt

## Enhanced Retry with Jitter

### Configuration
```python
class ProcessingConfig(BaseModel):
    mode: str = "async"
    batch_size: int = 10
    max_retries: int = 3              # Used by LLMClient
    circuit_breaker_threshold: int = 5  # New field
    checkin_interval: int | None = None
```

### Retry Strategy
- **Backoff**: Exponential with jitter
- **Formula**: `delay = base * 2^attempt * (0.5 + random())`
- **Bounds**: min=1s, max=60s
- **Jitter range**: 50%-150% of calculated delay

### Tenacity Implementation
```python
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

@retry(
    retry=retry_if_exception_type(RETRYABLE_ERRORS),
    stop=stop_after_attempt(max_retries),
    wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
)
def _make_request(self, prompt: str, **kwargs) -> str:
    ...
```

### Fatal Error Handling
Fatal errors bypass retry entirely:
```python
def complete(self, prompt: str, **kwargs) -> str:
    try:
        return self._make_request(prompt, **kwargs)
    except FATAL_ERRORS:
        raise  # Don't retry, let circuit breaker handle
```

## Resume with --retry-failures

### CLI Usage
```bash
agents resume job_20251127_150640 --retry-failures
```

### Behavior Comparison
| Flag | Behavior |
|------|----------|
| Without flag | Skip items with any result (success or failure) |
| With flag | Re-process items with `error` or `parse_error` fields |

### Implementation
```python
# IncrementalWriter new method
def get_failed_indices(self) -> set[int]:
    """Get indices of failed items."""
    failed: set[int] = set()
    for line in self._read_lines():
        data = json.loads(line)
        if "error" in data or "parse_error" in data:
            failed.add(data.get("_idx"))
    return failed

# Resume logic
if retry_failures:
    failed_indices = writer.get_failed_indices()
    remaining = [u for u in all_units 
                 if u["_idx"] not in completed_indices 
                 or u["_idx"] in failed_indices]
```

### Result Deduplication
When retrying, new results replace old failures:
```python
def read_all_results(self) -> list[dict]:
    """Read results, keeping latest per _idx."""
    results_by_idx: dict[int, dict] = {}
    for line in self._read_lines():
        data = json.loads(line)
        idx = data.get("_idx")
        results_by_idx[idx] = data  # Later entries overwrite
    return sorted(results_by_idx.values(), key=lambda x: x.get("_idx", 0))
```

## File Changes

| File | Changes |
|------|---------|
| `agents/core/llm_client.py` | Add jitter, use `max_retries`, separate fatal vs retryable |
| `agents/core/engine.py` | Add circuit breaker tracking, yield breaker events |
| `agents/core/circuit_breaker.py` | New file: `CircuitBreakerState` class |
| `agents/utils/config.py` | Add `circuit_breaker_threshold` field |
| `agents/utils/incremental_writer.py` | Add `get_failed_indices()`, deduplicate results |
| `agents/cli.py` | Add `--retry-failures` flag, handle breaker prompts |

## Async Mode Considerations

When circuit breaker triggers in async mode:
1. Stop dispatching new tasks
2. Wait for in-flight requests to complete
3. Collect their results (success or failure)
4. Then show prompt

This ensures no work is lost when the breaker trips.

## YAML Config Example

```yaml
llm:
  model: gpt-4o-mini
  api_key: ${OPENAI_API_KEY}

processing:
  mode: async
  batch_size: 10
  max_retries: 5
  circuit_breaker_threshold: 5

prompt: |
  Translate '{text}' to Spanish.
```
