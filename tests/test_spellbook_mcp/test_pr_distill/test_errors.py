"""Tests for pr_distill error types."""

import pytest
from spellbook_mcp.pr_distill.errors import ErrorCode, PRDistillError


class TestErrorCode:
    def test_error_codes_are_strings(self):
        assert ErrorCode.GH_NOT_AUTHENTICATED == "GH_NOT_AUTHENTICATED"
        assert ErrorCode.GH_PR_NOT_FOUND == "GH_PR_NOT_FOUND"
        assert ErrorCode.GH_RATE_LIMITED == "GH_RATE_LIMITED"
        assert ErrorCode.GH_NETWORK_ERROR == "GH_NETWORK_ERROR"
        assert ErrorCode.GH_VERSION_TOO_OLD == "GH_VERSION_TOO_OLD"
        assert ErrorCode.DIFF_PARSE_ERROR == "DIFF_PARSE_ERROR"
        assert ErrorCode.CONFIG_INVALID == "CONFIG_INVALID"
        assert ErrorCode.PATTERN_INVALID == "PATTERN_INVALID"

    def test_all_error_codes_defined(self):
        expected = {
            "GH_NOT_AUTHENTICATED",
            "GH_PR_NOT_FOUND",
            "GH_RATE_LIMITED",
            "GH_NETWORK_ERROR",
            "GH_VERSION_TOO_OLD",
            "DIFF_PARSE_ERROR",
            "CONFIG_INVALID",
            "PATTERN_INVALID",
        }
        actual = {e.value for e in ErrorCode}
        assert actual == expected


class TestPRDistillError:
    def test_error_creation(self):
        error = PRDistillError(
            code=ErrorCode.GH_PR_NOT_FOUND,
            message="PR 123 not found",
            recoverable=False,
            context={"pr_number": 123}
        )
        assert error.code == ErrorCode.GH_PR_NOT_FOUND
        assert str(error) == "PR 123 not found"
        assert error.recoverable is False
        assert error.context == {"pr_number": 123}

    def test_error_default_context(self):
        error = PRDistillError(
            code=ErrorCode.GH_NETWORK_ERROR,
            message="Network timeout",
            recoverable=True
        )
        assert error.context == {}

    def test_user_message(self):
        error = PRDistillError(
            code=ErrorCode.GH_RATE_LIMITED,
            message="Rate limit exceeded",
            recoverable=True
        )
        assert error.user_message() == "[GH_RATE_LIMITED] Rate limit exceeded"

    def test_error_is_exception(self):
        error = PRDistillError(
            code=ErrorCode.DIFF_PARSE_ERROR,
            message="Parse failed",
            recoverable=False
        )
        with pytest.raises(PRDistillError) as exc_info:
            raise error
        assert exc_info.value.code == ErrorCode.DIFF_PARSE_ERROR
