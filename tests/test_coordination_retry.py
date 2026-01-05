"""Test retry policy and error classification."""
import pytest


def test_error_category_enum():
    """Test ErrorCategory enum exists."""
    from spellbook_mcp.coordination.retry import ErrorCategory

    assert ErrorCategory.RECOVERABLE is not None
    assert ErrorCategory.NON_RECOVERABLE is not None


def test_classify_error_recoverable():
    """Test classifying recoverable errors."""
    from spellbook_mcp.coordination.retry import classify_error, ErrorCategory

    assert classify_error("network_error") == ErrorCategory.RECOVERABLE
    assert classify_error("rate_limit") == ErrorCategory.RECOVERABLE
    assert classify_error("test_flake") == ErrorCategory.RECOVERABLE
    assert classify_error("dependency_timeout") == ErrorCategory.RECOVERABLE


def test_classify_error_non_recoverable():
    """Test classifying non-recoverable errors."""
    from spellbook_mcp.coordination.retry import classify_error, ErrorCategory

    assert classify_error("test_failure") == ErrorCategory.NON_RECOVERABLE
    assert classify_error("build_failure") == ErrorCategory.NON_RECOVERABLE
    assert classify_error("merge_conflict") == ErrorCategory.NON_RECOVERABLE
    assert classify_error("invalid_manifest") == ErrorCategory.NON_RECOVERABLE


def test_classify_error_unknown_defaults_non_recoverable():
    """Test unknown error types default to non-recoverable."""
    from spellbook_mcp.coordination.retry import classify_error, ErrorCategory

    assert classify_error("unknown_error") == ErrorCategory.NON_RECOVERABLE
    assert classify_error("") == ErrorCategory.NON_RECOVERABLE


def test_retry_policy_default_values():
    """Test RetryPolicy default values."""
    from spellbook_mcp.coordination.retry import RetryPolicy

    policy = RetryPolicy()
    assert policy.max_retries == 2
    assert policy.backoff_base == 30
    assert policy.backoff_multiplier == 2


def test_retry_policy_get_retry_delay():
    """Test retry delay calculation."""
    from spellbook_mcp.coordination.retry import RetryPolicy

    policy = RetryPolicy()

    # Attempt 1: 30s
    assert policy.get_retry_delay(1) == 30

    # Attempt 2: 60s
    assert policy.get_retry_delay(2) == 60

    # Attempt 3 and beyond: 0 (no more retries)
    assert policy.get_retry_delay(3) == 0
    assert policy.get_retry_delay(4) == 0


def test_retry_policy_custom_values():
    """Test RetryPolicy with custom values."""
    from spellbook_mcp.coordination.retry import RetryPolicy

    policy = RetryPolicy(max_retries=3, backoff_base=10, backoff_multiplier=3)

    assert policy.get_retry_delay(1) == 10  # 10 * 3^0
    assert policy.get_retry_delay(2) == 30  # 10 * 3^1
    assert policy.get_retry_delay(3) == 90  # 10 * 3^2
    assert policy.get_retry_delay(4) == 0   # Exceeds max_retries
