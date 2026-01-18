"""Error types for PR distillation operations."""

from enum import Enum


class ErrorCode(str, Enum):
    """Error codes for PR distillation operations."""
    GH_NOT_AUTHENTICATED = "GH_NOT_AUTHENTICATED"
    GH_PR_NOT_FOUND = "GH_PR_NOT_FOUND"
    GH_RATE_LIMITED = "GH_RATE_LIMITED"
    GH_NETWORK_ERROR = "GH_NETWORK_ERROR"
    GH_VERSION_TOO_OLD = "GH_VERSION_TOO_OLD"
    DIFF_PARSE_ERROR = "DIFF_PARSE_ERROR"
    CONFIG_INVALID = "CONFIG_INVALID"
    PATTERN_INVALID = "PATTERN_INVALID"


class PRDistillError(Exception):
    """Structured error for PR distillation."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        recoverable: bool = False,
        context: dict = None
    ):
        super().__init__(message)
        self.code = code
        self.recoverable = recoverable
        self.context = context or {}

    def user_message(self) -> str:
        """Return formatted message for display to user."""
        return f"[{self.code.value}] {self.args[0]}"
