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
    """Tracks consecutive failures and trips when threshold reached."""

    threshold: int = 5
    consecutive_failures: int = field(default=0, init=False)
    last_error: Exception | None = field(default=None, init=False)
    last_failed_unit: dict[str, Any] | None = field(default=None, init=False)

    def record_failure(self, error: Exception, unit: dict[str, Any]) -> None:
        """Record a failure and update state."""
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
        """Check if circuit breaker has tripped."""
        return self.consecutive_failures >= self.threshold

    def get_status(self) -> dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "consecutive_failures": self.consecutive_failures,
            "threshold": self.threshold,
            "is_tripped": self.is_tripped(),
            "last_error_type": type(self.last_error).__name__ if self.last_error else None,
            "last_error_message": str(self.last_error) if self.last_error else None,
            "last_failed_unit": self.last_failed_unit,
        }
