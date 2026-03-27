"""Security feature installation component.

Handles configuration of all injection defense features during
the installation process.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _config_set(key: str, value: Any) -> None:
    """Write a config value via spellbook's config store.

    This is a thin wrapper so tests can mock the write path without
    importing the full spellbook config machinery.
    """
    from spellbook.core.config import config_set
    config_set(key, value)


def get_security_config_keys() -> List[str]:
    """Return all security configuration keys."""
    return [
        # Spotlighting
        "security.spotlighting.enabled",
        "security.spotlighting.tier",
        "security.spotlighting.mcp_wrap",
        "security.spotlighting.custom_prefix",
        # Cryptographic Provenance
        "security.crypto.enabled",
        "security.crypto.keys_dir",
        "security.crypto.gate_spawn_session",
        "security.crypto.gate_workflow_save",
        "security.crypto.gate_config_writes",
        "security.crypto.auto_sign_on_install",
        # PromptSleuth
        "security.sleuth.enabled",
        "security.sleuth.api_key",
        "security.sleuth.max_content_bytes",
        "security.sleuth.max_tokens_per_check",
        "security.sleuth.calls_per_session",
        "security.sleuth.confidence_threshold",
        "security.sleuth.cache_ttl_seconds",
        "security.sleuth.timeout_seconds",
        "security.sleuth.fallback_on_budget_exceeded",
        # LODO Evaluation
        "security.lodo.datasets_dir",
        "security.lodo.min_detection_rate",
        "security.lodo.max_false_positive_rate",
    ]


def get_default_security_config() -> Dict[str, Any]:
    """Return default values for all security config keys."""
    return {
        # Spotlighting
        "security.spotlighting.enabled": True,
        "security.spotlighting.tier": "standard",
        "security.spotlighting.mcp_wrap": True,
        "security.spotlighting.custom_prefix": "",
        # Cryptographic Provenance
        "security.crypto.enabled": True,
        "security.crypto.keys_dir": "~/.local/spellbook/keys",
        "security.crypto.gate_spawn_session": True,
        "security.crypto.gate_workflow_save": True,
        "security.crypto.gate_config_writes": False,
        "security.crypto.auto_sign_on_install": True,
        # PromptSleuth (disabled by default -- requires API key)
        "security.sleuth.enabled": False,
        "security.sleuth.api_key": None,
        "security.sleuth.max_content_bytes": 50000,
        "security.sleuth.max_tokens_per_check": 1024,
        "security.sleuth.calls_per_session": 50,
        "security.sleuth.confidence_threshold": 0.8,
        "security.sleuth.cache_ttl_seconds": 3600,
        "security.sleuth.timeout_seconds": 5,
        "security.sleuth.fallback_on_budget_exceeded": "regex_only",
        # LODO Evaluation
        "security.lodo.datasets_dir": "tests/test_security/datasets",
        "security.lodo.min_detection_rate": 0.85,
        "security.lodo.max_false_positive_rate": 0.05,
    }


# Mapping from feature id to the config key prefix it controls
_FEATURE_PREFIXES: Dict[str, str] = {
    "spotlighting": "security.spotlighting.",
    "crypto": "security.crypto.",
    "sleuth": "security.sleuth.",
    "lodo": "security.lodo.",
}


def apply_security_config(
    selections: Dict[str, bool],
    dry_run: bool = False,
) -> List[str]:
    """Apply security feature configuration based on user selections.

    For each selected feature, writes the default config values.  For
    deselected features, sets ``<prefix>.enabled`` to False (if the key
    exists) but still writes the remaining defaults so the config store
    has a complete schema.

    Args:
        selections: Mapping of feature id (e.g. ``"spotlighting"``) to
            enabled/disabled bool.
        dry_run: If True, return the list of keys that *would* be written
            without actually writing anything.

    Returns:
        List of config keys that were (or would be) written.
    """
    defaults = get_default_security_config()
    written_keys: List[str] = []

    for feature_id, enabled in selections.items():
        prefix = _FEATURE_PREFIXES.get(feature_id)
        if prefix is None:
            continue

        for key, default_value in defaults.items():
            if not key.startswith(prefix):
                continue

            # Override the .enabled key with the user's selection
            if key.endswith(".enabled"):
                value = enabled
            else:
                value = default_value

            written_keys.append(key)
            if not dry_run:
                _config_set(key, value)

    return written_keys


_SECURITY_LEVEL_PRESETS: Dict[str, Dict[str, bool]] = {
    # Minimal: only passive content isolation; no key generation or API calls.
    "minimal": {
        "spotlighting": True,
        "crypto": False,
        "sleuth": False,
        "lodo": False,
    },
    # Standard: passive isolation + cryptographic provenance (default wizard choice).
    "standard": {
        "spotlighting": True,
        "crypto": True,
        "sleuth": False,
        "lodo": False,
    },
    # Strict: all defenses enabled; sleuth requires an API key configured separately.
    "strict": {
        "spotlighting": True,
        "crypto": True,
        "sleuth": True,
        "lodo": True,
    },
}


def security_level_to_selections(level: str) -> Dict[str, bool]:
    """Convert a named security level to a feature-selections dict.

    Args:
        level: One of ``"minimal"``, ``"standard"``, or ``"strict"``.

    Returns:
        Mapping of feature id to enabled bool, suitable for passing to
        :func:`apply_security_config` or ``Installer.run(security_selections=...)``.

    Raises:
        ValueError: If *level* is not a recognised preset name.
    """
    try:
        return dict(_SECURITY_LEVEL_PRESETS[level])
    except KeyError:
        valid = ", ".join(sorted(_SECURITY_LEVEL_PRESETS))
        raise ValueError(f"Unknown security level {level!r}. Valid levels: {valid}")


def get_security_summary(selections: Dict[str, bool]) -> str:
    """Return a human-readable summary of security feature selections.

    Args:
        selections: Mapping of feature id to enabled bool.

    Returns:
        Multi-line string describing what is enabled/disabled.
    """
    feature_display = {
        "spotlighting": "Spotlighting (delimiter-based content isolation)",
        "crypto": "Cryptographic Provenance (Ed25519 signing)",
        "sleuth": "PromptSleuth (semantic intent classification)",
        "lodo": "LODO Evaluation (regex detection benchmarking)",
    }

    lines: List[str] = []
    for feat_id, enabled in selections.items():
        name = feature_display.get(feat_id, feat_id)
        status = "ENABLED" if enabled else "disabled"
        lines.append(f"  {name}: {status}")

    return "\n".join(lines) if lines else "  No security features configured."
