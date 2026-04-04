"""Upfront wizard data types and helpers.

Defines the input context and output results for the consolidated
installer wizard that collects all user decisions before installation
begins.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class WizardContext:
    """Input context for the upfront wizard.

    Assembled by run_installation() from CLI args, detected state,
    and existing configuration. Tells the wizard what to ask and
    what to skip.
    """

    # Platform selection
    available_platforms: list[str]
    cli_platforms: list[str] | None

    # Security config
    unset_security_keys: list[str]
    existing_config: dict[str, Any]
    security_level: str | None

    # TTS
    tts_disabled: bool
    tts_already_configured: bool

    # Profile
    profile_already_configured: bool
    available_profiles: list[Any]

    # Install metadata
    is_upgrade: bool
    is_interactive: bool
    auto_yes: bool
    no_interactive: bool
    reconfigure: bool


@dataclass
class WizardResults:
    """Consolidated output from the upfront wizard.

    Every field has a sentinel value meaning "not asked / use default":

    - platforms: None means "not asked, use auto-detect".
      A list (even empty) means the user made an explicit selection.
    - security_selections: None means "not asked" (either CLI flag
      handled it, or no unset keys). Dict maps dotted config keys
      (e.g. "security.crypto.enabled") to bool. The caller converts
      these to bare feature IDs before passing to Installer.run().
    - tts_intent: None means "not asked / already configured".
      True means user wants TTS enabled. False means user declined or
      --no-tts was passed.
    - profile_selection: None means "not asked / already configured".
      A slug string (e.g. "zen") means user picked a profile.
      Empty string "" means user explicitly chose "None" (no profile).
    """

    platforms: list[str] | None = None
    security_selections: dict[str, bool] | None = None
    tts_intent: bool | None = None
    profile_selection: str | None = None


def _matches_unset_key(feature_id: str, unset_keys: list[str]) -> bool:
    """Check if a feature ID matches any unset config key.

    Feature IDs are bare (e.g. "spotlighting"), while unset_keys are
    dotted (e.g. "security.spotlighting.enabled"). Match by checking
    if the feature ID appears as a complete segment in the dotted key.

    Args:
        feature_id: Bare feature identifier (e.g. "crypto").
        unset_keys: List of dotted config key strings
            (e.g. ["security.crypto.enabled"]).

    Returns:
        True if feature_id appears as a dot-delimited segment in any key.
    """
    return any(
        f".{feature_id}." in key or key.startswith(f"{feature_id}.")
        for key in unset_keys
    )
