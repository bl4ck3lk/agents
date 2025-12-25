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
