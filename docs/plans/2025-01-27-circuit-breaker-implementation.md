# Circuit Breaker & Enhanced Retry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add circuit breaker, enhanced retry with jitter, and `--retry-failures` flag to prevent cascading failures and enable re-processing of failed items.

**Architecture:** Circuit breaker lives in engine, tracks consecutive fatal errors, yields special events for CLI to handle. LLM client separates fatal vs retryable errors with jitter-based backoff. IncrementalWriter deduplicates results to support retry.

**Tech Stack:** Python 3.11+, tenacity (retry), click (CLI), pydantic (config)

---

## Task 1: Add `circuit_breaker_threshold` to Config

**Files:**
- Modify: `agents/utils/config.py:17-23`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_processing_config_circuit_breaker_threshold() -> None:
    """Test circuit_breaker_threshold has default value."""
    config = ProcessingConfig()
    assert config.circuit_breaker_threshold == 5
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_processing_config_circuit_breaker_threshold -v`
Expected: FAIL with `AttributeError: 'ProcessingConfig' object has no attribute 'circuit_breaker_threshold'`

**Step 3: Write minimal implementation**

In `agents/utils/config.py`, update `ProcessingConfig`:

```python
class ProcessingConfig(BaseModel):
    """Processing configuration."""

    mode: str = "async"
    batch_size: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0
    checkin_interval: int | None = None
    circuit_breaker_threshold: int = 5  # New field
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_processing_config_circuit_breaker_threshold -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/utils/config.py tests/test_config.py
git commit -m "feat(config): add circuit_breaker_threshold setting"
```

---

## Task 2: Create CircuitBreaker Class

**Files:**
- Create: `agents/core/circuit_breaker.py`
- Create: `tests/test_circuit_breaker.py`

**Step 1: Write the failing test**

Create `tests/test_circuit_breaker.py`:

```python
"""Tests for circuit breaker."""

import pytest

from agents.core.circuit_breaker import CircuitBreaker, CircuitBreakerTripped


def test_circuit_breaker_initial_state() -> None:
    """Test circuit breaker starts with zero failures."""
    cb = CircuitBreaker(threshold=5)
    assert cb.consecutive_failures == 0
    assert cb.last_error is None
    assert cb.last_failed_unit is None
    assert not cb.is_tripped()


def test_circuit_breaker_records_failure() -> None:
    """Test circuit breaker tracks failures."""
    cb = CircuitBreaker(threshold=5)
    error = Exception("test error")
    unit = {"id": "1", "text": "hello"}
    
    cb.record_failure(error, unit)
    
    assert cb.consecutive_failures == 1
    assert cb.last_error is error
    assert cb.last_failed_unit is unit


def test_circuit_breaker_resets_on_success() -> None:
    """Test circuit breaker resets counter on success."""
    cb = CircuitBreaker(threshold=5)
    cb.record_failure(Exception("err"), {"id": "1"})
    cb.record_failure(Exception("err"), {"id": "2"})
    assert cb.consecutive_failures == 2
    
    cb.record_success()
    
    assert cb.consecutive_failures == 0
    assert cb.last_error is None
    assert cb.last_failed_unit is None


def test_circuit_breaker_trips_at_threshold() -> None:
    """Test circuit breaker trips after threshold failures."""
    cb = CircuitBreaker(threshold=3)
    
    for i in range(3):
        cb.record_failure(Exception(f"err{i}"), {"id": str(i)})
    
    assert cb.is_tripped()
    assert cb.consecutive_failures == 3


def test_circuit_breaker_manual_reset() -> None:
    """Test circuit breaker can be manually reset."""
    cb = CircuitBreaker(threshold=3)
    for i in range(3):
        cb.record_failure(Exception(f"err{i}"), {"id": str(i)})
    assert cb.is_tripped()
    
    cb.reset()
    
    assert not cb.is_tripped()
    assert cb.consecutive_failures == 0


def test_circuit_breaker_get_status() -> None:
    """Test circuit breaker returns status dict."""
    cb = CircuitBreaker(threshold=5)
    cb.record_failure(ValueError("bad value"), {"id": "123", "text": "test"})
    
    status = cb.get_status()
    
    assert status["consecutive_failures"] == 1
    assert status["threshold"] == 5
    assert status["is_tripped"] is False
    assert status["last_error_type"] == "ValueError"
    assert status["last_error_message"] == "bad value"
    assert status["last_failed_unit"] == {"id": "123", "text": "test"}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_circuit_breaker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.core.circuit_breaker'`

**Step 3: Write minimal implementation**

Create `agents/core/circuit_breaker.py`:

```python
"""Circuit breaker for fault tolerance."""

from dataclasses import dataclass, field
from typing import Any


class CircuitBreakerTripped(Exception):
    """Raised when circuit breaker threshold is reached."""

    def __init__(self, status: dict[str, Any]) -> None:
        self.status = status
        super().__init__(f"Circuit breaker tripped after {status['consecutive_failures']} failures")


@dataclass
class CircuitBreaker:
    """Tracks consecutive failures and trips when threshold reached.
    
    The circuit breaker monitors for fatal errors (non-retryable) and
    trips after a configurable number of consecutive failures, allowing
    the user to inspect and decide whether to continue.
    """

    threshold: int = 5
    consecutive_failures: int = field(default=0, init=False)
    last_error: Exception | None = field(default=None, init=False)
    last_failed_unit: dict[str, Any] | None = field(default=None, init=False)

    def record_failure(self, error: Exception, unit: dict[str, Any]) -> None:
        """Record a failure and update state.
        
        Args:
            error: The exception that caused the failure.
            unit: The data unit that failed.
        """
        self.consecutive_failures += 1
        self.last_error = error
        self.last_failed_unit = unit

    def record_success(self) -> None:
        """Record a success, resetting the failure counter."""
        self.consecutive_failures = 0
        self.last_error = None
        self.last_failed_unit = None

    def reset(self) -> None:
        """Manually reset the circuit breaker state."""
        self.consecutive_failures = 0
        self.last_error = None
        self.last_failed_unit = None

    def is_tripped(self) -> bool:
        """Check if circuit breaker has tripped.
        
        Returns:
            True if consecutive failures >= threshold.
        """
        return self.consecutive_failures >= self.threshold

    def get_status(self) -> dict[str, Any]:
        """Get current circuit breaker status.
        
        Returns:
            Dict with failure count, threshold, error details.
        """
        return {
            "consecutive_failures": self.consecutive_failures,
            "threshold": self.threshold,
            "is_tripped": self.is_tripped(),
            "last_error_type": type(self.last_error).__name__ if self.last_error else None,
            "last_error_message": str(self.last_error) if self.last_error else None,
            "last_failed_unit": self.last_failed_unit,
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_circuit_breaker.py -v`
Expected: PASS (all 6 tests)

**Step 5: Commit**

```bash
git add agents/core/circuit_breaker.py tests/test_circuit_breaker.py
git commit -m "feat(core): add CircuitBreaker class for fault tolerance"
```

---

## Task 3: Enhance LLMClient with Jitter and Error Classification

**Files:**
- Modify: `agents/core/llm_client.py`
- Modify: `tests/test_llm_client.py`

**Step 1: Write the failing tests**

Add to `tests/test_llm_client.py`:

```python
from openai import AuthenticationError, PermissionDeniedError

from agents.core.llm_client import FATAL_ERRORS, RETRYABLE_ERRORS, FatalLLMError


def test_fatal_errors_defined() -> None:
    """Test FATAL_ERRORS tuple is defined."""
    assert AuthenticationError in FATAL_ERRORS
    assert PermissionDeniedError in FATAL_ERRORS


def test_retryable_errors_defined() -> None:
    """Test RETRYABLE_ERRORS tuple is defined."""
    assert RateLimitError in RETRYABLE_ERRORS


def test_llm_client_raises_fatal_error_without_retry(mock_openai_client: Mock) -> None:
    """Test fatal errors are raised immediately without retry."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_openai_client.chat.completions.create.side_effect = AuthenticationError(
        "Invalid API key", response=mock_response, body=None
    )

    with patch("agents.core.llm_client.OpenAI", return_value=mock_openai_client):
        client = LLMClient(api_key="bad-key", model="gpt-4o-mini")
        with pytest.raises(FatalLLMError) as exc_info:
            client.complete("Test")
    
    # Should only be called once - no retries for fatal errors
    assert mock_openai_client.chat.completions.create.call_count == 1
    assert "AuthenticationError" in str(exc_info.value)


def test_llm_client_uses_max_retries_param(mock_openai_client: Mock) -> None:
    """Test client respects max_retries parameter."""
    mock_openai_client.chat.completions.create.side_effect = RateLimitError(
        "Rate limit", response=Mock(), body=None
    )

    with patch("agents.core.llm_client.OpenAI", return_value=mock_openai_client):
        client = LLMClient(api_key="test-key", model="gpt-4o-mini", max_retries=5)
        with pytest.raises(Exception):  # Will fail after 5 retries
            client.complete("Test")
    
    assert mock_openai_client.chat.completions.create.call_count == 5
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm_client.py::test_fatal_errors_defined tests/test_llm_client.py::test_llm_client_raises_fatal_error_without_retry -v`
Expected: FAIL with `ImportError: cannot import name 'FATAL_ERRORS'`

**Step 3: Write implementation**

Replace `agents/core/llm_client.py`:

```python
"""LLM client wrapper for OpenAI API."""

from typing import Any

from openai import (
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

# Fatal errors - don't retry, surface immediately
FATAL_ERRORS = (AuthenticationError, PermissionDeniedError, BadRequestError)

# Retryable errors - retry with exponential backoff + jitter
RETRYABLE_ERRORS = (RateLimitError, APITimeoutError, APIError)


class FatalLLMError(Exception):
    """Wrapper for fatal LLM errors that should not be retried."""

    def __init__(self, original_error: Exception) -> None:
        self.original_error = original_error
        self.error_type = type(original_error).__name__
        super().__init__(f"{self.error_type}: {original_error}")


class LLMClient:
    """Client for interacting with LLM APIs."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1500,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize LLM client.

        Args:
            api_key: API key for authentication.
            model: Model name to use.
            base_url: Optional base URL for API endpoint.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            max_retries: Maximum retry attempts for transient errors.
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    def _make_request(self, prompt: str, **kwargs: Any) -> str:
        """Make API request with retry logic for transient errors.
        
        Fatal errors (auth, permission, bad request) are raised immediately.
        Retryable errors use exponential backoff with jitter.
        """
        # Build retry decorator dynamically to use instance max_retries
        @retry(
            retry=retry_if_exception_type(RETRYABLE_ERRORS),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
            reraise=True,
        )
        def _request() -> str:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
            )
            return response.choices[0].message.content or ""

        return _request()

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """
        Generate completion for prompt.

        Args:
            prompt: Input prompt.
            **kwargs: Additional arguments for API call.

        Returns:
            Generated text response.

        Raises:
            FatalLLMError: For authentication/permission errors (no retry).
        """
        try:
            return self._make_request(prompt, **kwargs)
        except FATAL_ERRORS as e:
            raise FatalLLMError(e) from e

    async def _make_request_async(self, prompt: str, **kwargs: Any) -> str:
        """Make async API request with retry logic."""
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(RETRYABLE_ERRORS),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
            reraise=True,
        ):
            with attempt:
                response = await self.async_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                )
                return response.choices[0].message.content or ""

        raise RuntimeError("Async retry loop exited unexpectedly")

    async def complete_async(self, prompt: str, **kwargs: Any) -> str:
        """
        Generate completion for prompt asynchronously.

        Args:
            prompt: Input prompt.
            **kwargs: Additional arguments for API call.

        Returns:
            Generated text response.

        Raises:
            FatalLLMError: For authentication/permission errors (no retry).
        """
        try:
            return await self._make_request_async(prompt, **kwargs)
        except FATAL_ERRORS as e:
            raise FatalLLMError(e) from e
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_llm_client.py -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add agents/core/llm_client.py tests/test_llm_client.py
git commit -m "feat(llm): add jitter, error classification, use max_retries param"
```

---

## Task 4: Add `get_failed_indices()` and Deduplicate Results

**Files:**
- Modify: `agents/utils/incremental_writer.py`
- Create: `tests/test_incremental_writer.py`

**Step 1: Write the failing tests**

Create `tests/test_incremental_writer.py`:

```python
"""Tests for incremental writer."""

import json
import tempfile
from pathlib import Path

import pytest

from agents.utils.incremental_writer import IncrementalWriter


@pytest.fixture
def temp_checkpoint_dir():
    """Create temporary checkpoint directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_get_failed_indices_returns_empty_for_new_job(temp_checkpoint_dir: Path) -> None:
    """Test get_failed_indices returns empty set for new job."""
    writer = IncrementalWriter("test_job", temp_checkpoint_dir)
    assert writer.get_failed_indices() == set()


def test_get_failed_indices_finds_errors(temp_checkpoint_dir: Path) -> None:
    """Test get_failed_indices returns indices of items with errors."""
    writer = IncrementalWriter("test_job", temp_checkpoint_dir)
    
    writer.write_result({"_idx": 0, "text": "ok", "result": "success"})
    writer.write_result({"_idx": 1, "text": "bad", "error": "API error"})
    writer.write_result({"_idx": 2, "text": "ok2", "result": "success"})
    writer.write_result({"_idx": 3, "text": "parse_fail", "parse_error": "Invalid JSON"})
    
    failed = writer.get_failed_indices()
    
    assert failed == {1, 3}


def test_read_all_results_deduplicates_by_idx(temp_checkpoint_dir: Path) -> None:
    """Test read_all_results keeps latest result per _idx."""
    writer = IncrementalWriter("test_job", temp_checkpoint_dir)
    
    # First run: some failures
    writer.write_result({"_idx": 0, "text": "a", "result": "ok"})
    writer.write_result({"_idx": 1, "text": "b", "error": "failed"})
    writer.write_result({"_idx": 2, "text": "c", "result": "ok"})
    
    # Retry run: idx 1 succeeds
    writer.write_result({"_idx": 1, "text": "b", "result": "now ok"})
    
    results = writer.read_all_results()
    
    assert len(results) == 3
    assert results[0] == {"_idx": 0, "text": "a", "result": "ok"}
    assert results[1] == {"_idx": 1, "text": "b", "result": "now ok"}  # Updated!
    assert results[2] == {"_idx": 2, "text": "c", "result": "ok"}


def test_read_all_results_handles_multiple_retries(temp_checkpoint_dir: Path) -> None:
    """Test deduplication works with multiple retry attempts."""
    writer = IncrementalWriter("test_job", temp_checkpoint_dir)
    
    # Original
    writer.write_result({"_idx": 5, "error": "first failure"})
    # First retry
    writer.write_result({"_idx": 5, "error": "second failure"})
    # Second retry
    writer.write_result({"_idx": 5, "result": "finally worked"})
    
    results = writer.read_all_results()
    
    assert len(results) == 1
    assert results[0] == {"_idx": 5, "result": "finally worked"}
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_incremental_writer.py -v`
Expected: FAIL with `AttributeError: 'IncrementalWriter' object has no attribute 'get_failed_indices'`

**Step 3: Write implementation**

Update `agents/utils/incremental_writer.py`. Add `get_failed_indices()` method and modify `read_all_results()`:

```python
def get_failed_indices(self) -> set[int]:
    """
    Get indices of failed items (have error or parse_error).

    Returns:
        Set of indices that failed.
    """
    failed: set[int] = set()
    if not self.path.exists():
        return failed

    with open(self.path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if any(key in data for key in FAILURE_KEYS):
                    idx = data.get("_idx")
                    if idx is not None:
                        failed.add(idx)
            except json.JSONDecodeError:
                continue

    return failed

def read_all_results(self) -> list[dict[str, Any]]:
    """
    Read all results from JSONL, deduplicated by _idx (latest wins).

    When retrying failures, new results are appended. This method
    keeps only the latest result for each _idx.

    Returns:
        List of results sorted by _idx, deduplicated.
    """
    results_by_idx: dict[int, dict[str, Any]] = {}
    results_no_idx: list[dict[str, Any]] = []
    
    if not self.path.exists():
        return []

    with open(self.path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                idx = data.get("_idx")
                if idx is not None:
                    results_by_idx[idx] = data  # Later entries overwrite
                else:
                    results_no_idx.append(data)
            except json.JSONDecodeError:
                continue

    # Sort by _idx
    sorted_results = sorted(results_by_idx.values(), key=lambda x: x.get("_idx", 0))
    return sorted_results + results_no_idx
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_incremental_writer.py -v`
Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add agents/utils/incremental_writer.py tests/test_incremental_writer.py
git commit -m "feat(writer): add get_failed_indices, deduplicate results by _idx"
```

---

## Task 5: Integrate Circuit Breaker into ProcessingEngine

**Files:**
- Modify: `agents/core/engine.py`
- Modify: `tests/test_engine.py`

**Step 1: Write the failing tests**

Add to `tests/test_engine.py`:

```python
from agents.core.circuit_breaker import CircuitBreakerTripped
from agents.core.llm_client import FatalLLMError


def test_engine_tracks_fatal_errors_in_circuit_breaker(mock_llm_client: Mock) -> None:
    """Test engine counts fatal errors toward circuit breaker."""
    # Simulate fatal error
    mock_llm_client.complete.side_effect = FatalLLMError(Exception("Permission denied"))

    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(
        mock_llm_client,
        template,
        mode=ProcessingMode.SEQUENTIAL,
        circuit_breaker_threshold=3,
    )

    units = [{"text": f"item{i}"} for i in range(5)]
    results = []
    
    with pytest.raises(CircuitBreakerTripped) as exc_info:
        for result in engine.process(units):
            results.append(result)
    
    # Should have processed 3 items before tripping
    assert len(results) == 3
    assert exc_info.value.status["consecutive_failures"] == 3


def test_engine_resets_circuit_breaker_on_success(mock_llm_client: Mock) -> None:
    """Test circuit breaker resets after successful processing."""
    # Fail twice, then succeed
    mock_llm_client.complete.side_effect = [
        FatalLLMError(Exception("err1")),
        FatalLLMError(Exception("err2")),
        "Success",
        "Success",
    ]

    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(
        mock_llm_client,
        template,
        mode=ProcessingMode.SEQUENTIAL,
        circuit_breaker_threshold=3,
    )

    units = [{"text": f"item{i}"} for i in range(4)]
    results = list(engine.process(units))
    
    # All 4 should process (breaker never trips because success resets counter)
    assert len(results) == 4
    assert "error" in results[0]
    assert "error" in results[1]
    assert results[2]["result"] == "Success"
    assert results[3]["result"] == "Success"


def test_engine_circuit_breaker_disabled_when_zero(mock_llm_client: Mock) -> None:
    """Test circuit breaker is disabled when threshold is 0."""
    mock_llm_client.complete.side_effect = FatalLLMError(Exception("err"))

    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(
        mock_llm_client,
        template,
        mode=ProcessingMode.SEQUENTIAL,
        circuit_breaker_threshold=0,  # Disabled
    )

    units = [{"text": f"item{i}"} for i in range(10)]
    results = list(engine.process(units))
    
    # All 10 should process (no circuit breaker)
    assert len(results) == 10
    assert all("error" in r for r in results)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_engine.py::test_engine_tracks_fatal_errors_in_circuit_breaker -v`
Expected: FAIL with `TypeError: ProcessingEngine.__init__() got an unexpected keyword argument 'circuit_breaker_threshold'`

**Step 3: Write implementation**

Update `agents/core/engine.py`:

```python
"""Processing engine for batch LLM operations."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from enum import Enum
from typing import Any

from agents.core.circuit_breaker import CircuitBreaker, CircuitBreakerTripped
from agents.core.llm_client import FatalLLMError, LLMClient
from agents.core.postprocessor import PostProcessor
from agents.core.prompt import PromptTemplate

# Key used to indicate parse failure in results
PARSE_ERROR_KEY = "parse_error"


class ProcessingMode(str, Enum):
    """Processing mode for engine."""

    SEQUENTIAL = "sequential"
    ASYNC = "async"


class ProcessingEngine:
    """Engine for processing data units with LLM."""

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_template: PromptTemplate,
        mode: ProcessingMode = ProcessingMode.SEQUENTIAL,
        batch_size: int = 10,
        post_process: bool = True,
        merge_results: bool = True,
        include_raw_result: bool = False,
        parse_error_retries: int = 2,
        circuit_breaker_threshold: int = 5,
    ) -> None:
        """
        Initialize processing engine.

        Args:
            llm_client: LLM client for API calls.
            prompt_template: Template for rendering prompts.
            mode: Processing mode (sequential or async).
            batch_size: Batch size for async mode.
            post_process: Whether to post-process LLM output to extract JSON.
            merge_results: Whether to merge parsed JSON fields into root.
            include_raw_result: Whether to include raw LLM output in result.
            parse_error_retries: Number of retries when JSON parsing fails.
            circuit_breaker_threshold: Consecutive fatal errors before tripping (0 to disable).
        """
        self.llm_client = llm_client
        self.prompt_template = prompt_template
        self.mode = mode
        self.batch_size = batch_size
        self.post_process = post_process
        self.merge_results = merge_results
        self.include_raw_result = include_raw_result
        self.parse_error_retries = parse_error_retries
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.post_processor = PostProcessor() if post_process else None
        
        # Initialize circuit breaker (disabled if threshold is 0)
        self._circuit_breaker: CircuitBreaker | None = None
        if circuit_breaker_threshold > 0:
            self._circuit_breaker = CircuitBreaker(threshold=circuit_breaker_threshold)

    def _check_circuit_breaker(self) -> None:
        """Check if circuit breaker has tripped and raise if so."""
        if self._circuit_breaker and self._circuit_breaker.is_tripped():
            raise CircuitBreakerTripped(self._circuit_breaker.get_status())

    def _record_fatal_error(self, error: Exception, unit: dict[str, Any]) -> None:
        """Record a fatal error in the circuit breaker."""
        if self._circuit_breaker:
            self._circuit_breaker.record_failure(error, unit)

    def _record_success(self) -> None:
        """Record a success, resetting the circuit breaker."""
        if self._circuit_breaker:
            self._circuit_breaker.record_success()

    def reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker (e.g., after user chooses to continue)."""
        if self._circuit_breaker:
            self._circuit_breaker.reset()

    def process(self, units: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """
        Process data units with LLM.

        Args:
            units: List of data units to process.

        Yields:
            Processed results with original data + result field.

        Raises:
            CircuitBreakerTripped: When consecutive fatal errors reach threshold.
        """
        if self.mode == ProcessingMode.SEQUENTIAL:
            yield from self._process_sequential(units)
        else:
            yield from self._process_async(units)

    def _process_single_unit(self, unit: dict[str, Any]) -> dict[str, Any]:
        """
        Process a single unit with retry logic for parse errors.

        Args:
            unit: Data unit to process.

        Returns:
            Processed result dict.

        Raises:
            FatalLLMError: Re-raised for circuit breaker handling.
        """
        last_result: dict[str, Any] | None = None
        attempts = 1 + self.parse_error_retries  # 1 initial + retries

        for attempt in range(attempts):
            try:
                prompt = self.prompt_template.render(unit)
                result = self.llm_client.complete(prompt)
                processed_result: dict[str, Any] = {**unit, "result": result}

                # Apply post-processing if enabled
                if self.post_processor:
                    processed_result = self.post_processor.process_result(
                        processed_result,
                        merge=self.merge_results,
                        include_raw=self.include_raw_result,
                    )

                # Check if parse error occurred
                if PARSE_ERROR_KEY not in processed_result:
                    return processed_result

                # Parse error - save result and retry
                last_result = processed_result
                if attempt < attempts - 1:
                    continue  # Retry

            except FatalLLMError:
                # Re-raise for circuit breaker handling in caller
                raise
            except Exception as e:
                return {**unit, "error": str(e)}

        # All retries exhausted, return last result with retry info
        if last_result:
            last_result["_retries_exhausted"] = True
            last_result["_attempts"] = attempts
            return last_result

        return {**unit, "error": "Unknown processing error"}

    def _process_sequential(self, units: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """Process units sequentially."""
        for unit in units:
            try:
                result = self._process_single_unit(unit)
                # Success - reset circuit breaker
                if "error" not in result:
                    self._record_success()
                yield result
            except FatalLLMError as e:
                # Record fatal error and yield error result
                self._record_fatal_error(e.original_error, unit)
                yield {**unit, "error": str(e)}
                # Check if we should trip
                self._check_circuit_breaker()

    def _process_async(self, units: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """Process units asynchronously using batch processing with incremental results."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async_gen = self._process_async_incremental(units)
            while True:
                try:
                    result = loop.run_until_complete(async_gen.__anext__())
                    yield result
                except StopAsyncIteration:
                    break
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    async def _process_single_unit_async(self, unit: dict[str, Any]) -> dict[str, Any]:
        """
        Process a single unit asynchronously with retry logic for parse errors.

        Args:
            unit: Data unit to process.

        Returns:
            Processed result dict.
        """
        last_result: dict[str, Any] | None = None
        attempts = 1 + self.parse_error_retries

        for attempt in range(attempts):
            try:
                prompt = self.prompt_template.render(unit)
                result = await self.llm_client.complete_async(prompt)
                processed_result: dict[str, Any] = {**unit, "result": result}

                if self.post_processor:
                    processed_result = self.post_processor.process_result(
                        processed_result,
                        merge=self.merge_results,
                        include_raw=self.include_raw_result,
                    )

                if PARSE_ERROR_KEY not in processed_result:
                    return processed_result

                last_result = processed_result
                if attempt < attempts - 1:
                    continue

            except FatalLLMError:
                raise
            except Exception as e:
                return {**unit, "error": str(e)}

        if last_result:
            last_result["_retries_exhausted"] = True
            last_result["_attempts"] = attempts
            return last_result

        return {**unit, "error": "Unknown processing error"}

    async def _process_async_incremental(
        self, units: list[dict[str, Any]]
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Process units asynchronously and yield results as they complete.

        Args:
            units: List of data units to process.

        Yields:
            Processed results as they complete.

        Raises:
            CircuitBreakerTripped: When consecutive fatal errors reach threshold.
        """
        semaphore = asyncio.Semaphore(self.batch_size)

        async def process_unit(unit: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                try:
                    return await self._process_single_unit_async(unit)
                except FatalLLMError as e:
                    return {**unit, "error": str(e), "_fatal": True, "_original_error": e}

        tasks = [asyncio.create_task(process_unit(unit)) for unit in units]

        for coro in asyncio.as_completed(tasks):
            result = await coro
            
            # Handle fatal errors for circuit breaker
            if result.get("_fatal"):
                original_error = result.pop("_original_error", None)
                result.pop("_fatal", None)
                if original_error:
                    self._record_fatal_error(original_error.original_error, result)
                self._check_circuit_breaker()
            elif "error" not in result:
                self._record_success()
            
            yield result
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_engine.py -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add agents/core/engine.py tests/test_engine.py
git commit -m "feat(engine): integrate circuit breaker for fatal error handling"
```

---

## Task 6: Add `--retry-failures` Flag to CLI

**Files:**
- Modify: `agents/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
from click.testing import CliRunner

from agents.cli import cli


def test_resume_retry_failures_flag_exists() -> None:
    """Test --retry-failures flag is accepted by resume command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["resume", "--help"])
    assert "--retry-failures" in result.output
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_resume_retry_failures_flag_exists -v`
Expected: FAIL with `AssertionError: assert '--retry-failures' in '...'`

**Step 3: Write implementation**

In `agents/cli.py`, update the `resume` command:

1. Add the flag:
```python
@cli.command()
@click.argument("job_id")
@click.option("--api-key", envvar="OPENAI_API_KEY", help="OpenAI API key")
@click.option(
    "--checkin-interval",
    type=int,
    default=None,
    help="Override check-in interval from original job",
)
@click.option(
    "--retry-failures",
    is_flag=True,
    default=False,
    help="Re-process items that failed with errors (instead of skipping them)",
)
def resume(job_id: str, api_key: str | None, checkin_interval: int | None, retry_failures: bool) -> None:
```

2. Update the filtering logic:
```python
# Initialize incremental writer and get completed indices
writer = IncrementalWriter(job_id, checkpoint_dir)
completed_indices = writer.get_completed_indices()

# Determine which units to process
if retry_failures:
    failed_indices = writer.get_failed_indices()
    # Process: not completed OR (completed but failed)
    remaining_units = [
        u for u in all_units 
        if u["_idx"] not in completed_indices or u["_idx"] in failed_indices
    ]
    click.echo(f"Found {len(failed_indices)} failed items to retry")
else:
    remaining_units = [u for u in all_units if u["_idx"] not in completed_indices]

click.echo(f"Found {len(completed_indices)} completed, {len(remaining_units)} remaining")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_resume_retry_failures_flag_exists -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/cli.py tests/test_cli.py
git commit -m "feat(cli): add --retry-failures flag to resume command"
```

---

## Task 7: Add Circuit Breaker Prompt Handling in CLI

**Files:**
- Modify: `agents/cli.py`

**Step 1: Update imports and add handler function**

Add to `agents/cli.py`:

```python
from agents.core.circuit_breaker import CircuitBreakerTripped


def handle_circuit_breaker(
    exc: CircuitBreakerTripped,
    tracker: ProgressTracker,
    writer: IncrementalWriter,
    processed_count: int,
    total_count: int,
) -> str:
    """
    Handle circuit breaker trip by prompting user.

    Args:
        exc: The CircuitBreakerTripped exception.
        tracker: Progress tracker for saving checkpoint.
        writer: Incremental writer for failure file.
        processed_count: Number processed so far.
        total_count: Total number of units.

    Returns:
        User choice: 'c' (continue), 'a' (abort), or 'i' (inspect).
    """
    status = exc.status
    
    click.echo("\n" + "=" * 60)
    click.echo(f"⚠️  Circuit breaker triggered: {status['consecutive_failures']} consecutive failures")
    click.echo("=" * 60)
    click.echo(f"\nLast error: {status['last_error_type']}")
    click.echo(f"Message: {status['last_error_message']}")
    
    if status['last_failed_unit']:
        # Truncate unit display for readability
        unit_str = str(status['last_failed_unit'])
        if len(unit_str) > 100:
            unit_str = unit_str[:100] + "..."
        click.echo(f"Failed unit: {unit_str}")
    
    success_count = processed_count - status['consecutive_failures']
    success_rate = (success_count / processed_count * 100) if processed_count > 0 else 0
    click.echo(f"\nProcessed: {processed_count}/{total_count} | Failed: {status['consecutive_failures']} | Success rate: {success_rate:.1f}%")
    
    # Save checkpoint before prompting
    tracker.save_checkpoint()
    
    click.echo("\n[C]ontinue  [A]bort  [I]nspect details")
    choice = click.prompt(
        ">",
        type=click.Choice(["c", "a", "i", "C", "A", "I"], case_sensitive=False),
        default="a",
    )
    
    return choice.lower()
```

**Step 2: Update process command to handle circuit breaker**

Wrap the processing loop in the `process` command:

```python
# In the process command, wrap the for loop:
try:
    for result in engine.process(units):
        writer.write_result(result)
        # ... existing logic ...
except CircuitBreakerTripped as exc:
    progress.stop()
    while True:
        choice = handle_circuit_breaker(exc, tracker, writer, processed_count, total_units)
        if choice == "c":
            # Continue - reset breaker and resume
            engine.reset_circuit_breaker()
            click.echo("\nResuming processing...")
            progress.start()
            # Continue from where we left off
            remaining = [u for u in units if u["_idx"] not in writer.get_completed_indices()]
            for result in engine.process(remaining):
                writer.write_result(result)
                # ... same logic ...
            break
        elif choice == "a":
            # Abort - save state and exit
            click.echo(f"\nAborted. To resume later: agents resume {job_id}")
            failures_path = writer.write_failures_file()
            if failures_path:
                click.echo(f"Failed items saved to: {failures_path}")
            return
        elif choice == "i":
            # Inspect - show full details and re-prompt
            click.echo("\n--- Full Error Details ---")
            click.echo(f"Error type: {exc.status['last_error_type']}")
            click.echo(f"Error message: {exc.status['last_error_message']}")
            click.echo(f"Failed unit: {json.dumps(exc.status['last_failed_unit'], indent=2, ensure_ascii=False)}")
            click.echo("-" * 40)
            continue  # Re-prompt
```

**Step 3: Apply same pattern to resume command**

Same circuit breaker handling in the `resume` command.

**Step 4: Run all tests**

Run: `pytest tests/ -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/cli.py
git commit -m "feat(cli): add circuit breaker prompt handling"
```

---

## Task 8: Wire Up Config to Engine and LLMClient

**Files:**
- Modify: `agents/cli.py`

**Step 1: Pass circuit_breaker_threshold to engine**

In the `process` command where `ProcessingEngine` is created:

```python
engine = ProcessingEngine(
    llm_client,
    prompt_template,
    mode=processing_mode,
    batch_size=final_batch_size,
    post_process=not no_post_process,
    merge_results=not no_merge,
    include_raw_result=include_raw,
    circuit_breaker_threshold=final_circuit_breaker_threshold,  # Add this
)
```

**Step 2: Add CLI option and config loading**

```python
@click.option(
    "--circuit-breaker",
    type=int,
    default=None,
    help="Trip after N consecutive fatal errors (default: 5, 0 to disable)",
)
def process(..., circuit_breaker: int | None, ...):
    # In config loading section:
    if config:
        # ... existing config loading ...
        final_circuit_breaker_threshold = (
            circuit_breaker 
            if circuit_breaker is not None 
            else job_config.processing.circuit_breaker_threshold
        )
    else:
        final_circuit_breaker_threshold = circuit_breaker if circuit_breaker is not None else 5
```

**Step 3: Pass max_retries to LLMClient**

```python
llm_client = LLMClient(
    api_key=final_api_key,
    model=final_model,
    base_url=final_base_url,
    max_tokens=final_max_tokens,
    max_retries=final_max_retries,  # Add this
)
```

**Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/cli.py
git commit -m "feat(cli): wire circuit_breaker_threshold and max_retries to config"
```

---

## Task 9: Final Integration Test

**Files:**
- Create: `tests/test_circuit_breaker_integration.py`

**Step 1: Write integration test**

```python
"""Integration tests for circuit breaker."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from agents.cli import cli
from agents.core.llm_client import FatalLLMError


def test_process_with_circuit_breaker_trip(tmp_path: Path) -> None:
    """Test full flow when circuit breaker trips."""
    # Create test input
    input_file = tmp_path / "input.jsonl"
    output_file = tmp_path / "output.jsonl"
    input_file.write_text('{"text": "hello"}\n' * 10)

    runner = CliRunner()
    
    with patch("agents.cli.LLMClient") as mock_client_class:
        mock_client = Mock()
        # Fail all requests with fatal error
        mock_client.complete.side_effect = FatalLLMError(Exception("Invalid API key"))
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            cli,
            [
                "process",
                str(input_file),
                str(output_file),
                "--prompt", "Test {text}",
                "--api-key", "test-key",
                "--circuit-breaker", "3",
            ],
            input="a\n",  # Abort when prompted
        )

    assert "Circuit breaker triggered" in result.output
    assert "3 consecutive failures" in result.output
```

**Step 2: Run integration test**

Run: `pytest tests/test_circuit_breaker_integration.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_circuit_breaker_integration.py
git commit -m "test: add circuit breaker integration tests"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add config field | `config.py`, `test_config.py` |
| 2 | Create CircuitBreaker class | `circuit_breaker.py`, `test_circuit_breaker.py` |
| 3 | Enhance LLMClient with jitter | `llm_client.py`, `test_llm_client.py` |
| 4 | Add get_failed_indices, dedupe | `incremental_writer.py`, `test_incremental_writer.py` |
| 5 | Integrate breaker into engine | `engine.py`, `test_engine.py` |
| 6 | Add --retry-failures flag | `cli.py`, `test_cli.py` |
| 7 | Add breaker prompt handling | `cli.py` |
| 8 | Wire config to components | `cli.py` |
| 9 | Integration tests | `test_circuit_breaker_integration.py` |

---

Plan complete and saved to `docs/plans/2025-01-27-circuit-breaker-implementation.md`.

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session in worktree with executing-plans, batch execution with checkpoints

**Which approach?**
