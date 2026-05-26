"""Field sanitization helper retained from the removed recovery-context chain.

The session-soul / recovery-injection chain (decorator, soul reader, compaction
signalling) was removed in 0.68.0. Only ``_sanitize_field`` survives: it is a
generic injection-pattern + length guard for DB-sourced strings, and it has a
live non-soul caller in ``spellbook.coordination.stint._validate_stint_entry``.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _sanitize_field(field_name: str, value: str, max_length: int) -> Optional[str]:
    """Sanitize a single DB-sourced field for injection patterns and length.

    Args:
        field_name: Name of the field (for logging).
        value: The field value to sanitize.
        max_length: Maximum allowed length.

    Returns:
        Sanitized value, or None if the field contains injection patterns.
    """
    if not value:
        return value

    # Truncate to length limit
    if len(value) > max_length:
        value = value[:max_length]

    # Check for injection patterns using the security detection
    try:
        from spellbook.gates.tools import do_detect_injection

        result = do_detect_injection(value)
        if result["is_injection"]:
            logger.warning(
                "Injection pattern detected in recovery context field '%s', "
                "omitting from context",
                field_name,
            )
            return None
    except ImportError:
        # Security module not installed; still apply length limits
        pass
    except Exception as e:
        # Unexpected error during security check: fail closed by omitting
        # the field rather than silently passing potentially dangerous input
        logger.warning(
            "Security check failed for field '%s', omitting as precaution: %s",
            field_name,
            type(e).__name__,
        )
        return None

    return value
