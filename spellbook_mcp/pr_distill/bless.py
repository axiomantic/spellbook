"""Pattern blessing with validation for PR distillation.

Provides validation and blessing functions for pattern IDs.
Pattern IDs must follow specific naming rules before they can be blessed.

Ported from lib/pr-distill/bless.js.
"""

import re

from spellbook_mcp.pr_distill.config import (
    load_config,
    save_config,
)


def validate_pattern_id(pattern_id: str) -> dict:
    """Validate a pattern ID against naming rules.

    Rules:
    - Length: 2-50 characters
    - Characters: [a-z0-9-] (lowercase letters, numbers, hyphens)
    - Must start with a letter
    - Must end with a letter or number
    - No double hyphens (--)
    - Cannot start with _builtin- (reserved prefix)

    Args:
        pattern_id: Pattern ID to validate

    Returns:
        {"valid": True} if valid, {"valid": False, "error": str} if invalid
    """
    # Check length
    if len(pattern_id) < 2 or len(pattern_id) > 50:
        return {
            "valid": False,
            "error": "Pattern ID must be 2-50 characters long",
        }

    # Check reserved prefix
    if pattern_id.startswith("_builtin-"):
        return {
            "valid": False,
            "error": 'Pattern ID cannot use reserved prefix "_builtin-"',
        }

    # Check valid characters (lowercase letters, numbers, hyphens only)
    if not re.match(r"^[a-z0-9-]+$", pattern_id):
        return {
            "valid": False,
            "error": "Pattern ID must contain only lowercase letters, numbers, and hyphens",
        }

    # Check starts with letter
    if not re.match(r"^[a-z]", pattern_id):
        return {
            "valid": False,
            "error": "Pattern ID must start with a letter",
        }

    # Check ends with letter or number
    if not re.search(r"[a-z0-9]$", pattern_id):
        return {
            "valid": False,
            "error": "Pattern ID must end with a letter or number",
        }

    # Check no double hyphens
    if "--" in pattern_id:
        return {
            "valid": False,
            "error": "Pattern ID cannot contain double hyphen (--)",
        }

    return {"valid": True}


def bless_pattern(project_root: str, pattern_id: str) -> dict:
    """Bless a pattern for a project.

    Validates the pattern ID and adds it to the blessed patterns list.

    Args:
        project_root: Absolute path to project root
        pattern_id: Pattern ID to bless

    Returns:
        {"success": True, "config": dict} on success,
        {"success": False, "error": str} on validation failure
    """
    validation = validate_pattern_id(pattern_id)
    if not validation["valid"]:
        return {
            "success": False,
            "error": validation["error"],
        }

    # Load existing config (or defaults)
    config = load_config(project_root)

    # Add pattern if not already present
    if pattern_id not in config["blessed_patterns"]:
        config["blessed_patterns"].append(pattern_id)

    # Save updated config
    save_config(project_root, config)

    return {
        "success": True,
        "config": config,
    }


def list_blessed_patterns(project_root: str) -> list[str]:
    """List all blessed patterns for a project.

    Args:
        project_root: Absolute path to project root

    Returns:
        List of blessed pattern IDs
    """
    config = load_config(project_root)
    return config["blessed_patterns"]
