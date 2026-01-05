"""Retry policy and error classification for coordination server."""
from enum import Enum
from dataclasses import dataclass


class ErrorCategory(Enum):
    """Classification of error types for retry decisions."""
    RECOVERABLE = "recoverable"
    NON_RECOVERABLE = "non_recoverable"


# Error types that can be retried
RECOVERABLE_ERRORS = {
    "network_error",
    "rate_limit",
    "test_flake",
    "dependency_timeout",
    "resource_unavailable",
}

# Error types that should not be retried
NON_RECOVERABLE_ERRORS = {
    "test_failure",
    "build_failure",
    "merge_conflict",
    "invalid_manifest",
    "authentication_failed",
    "validation_error",
    "missing_dependency",
}


def classify_error(error_type: str) -> ErrorCategory:
    """
    Classify an error as recoverable or non-recoverable.

    Args:
        error_type: The error type string

    Returns:
        ErrorCategory.RECOVERABLE or ErrorCategory.NON_RECOVERABLE
    """
    if error_type in RECOVERABLE_ERRORS:
        return ErrorCategory.RECOVERABLE
    else:
        # Default to non-recoverable for unknown errors (fail-safe)
        return ErrorCategory.NON_RECOVERABLE


@dataclass
class RetryPolicy:
    """Policy for retry attempts with exponential backoff."""

    max_retries: int = 2
    backoff_base: int = 30  # seconds
    backoff_multiplier: int = 2

    def get_retry_delay(self, attempt: int) -> int:
        """
        Calculate delay for retry attempt using exponential backoff.

        Args:
            attempt: Retry attempt number (1-indexed)

        Returns:
            Delay in seconds, or 0 if max retries exceeded
        """
        if attempt > self.max_retries:
            return 0

        # Exponential backoff: base * multiplier^(attempt-1)
        # Attempt 1: 30 * 2^0 = 30
        # Attempt 2: 30 * 2^1 = 60
        # Attempt 3: 30 * 2^2 = 120
        return self.backoff_base * (self.backoff_multiplier ** (attempt - 1))
