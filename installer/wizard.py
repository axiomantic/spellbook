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

    # Profile
    profile_already_configured: bool
    available_profiles: list[Any]

    # Install metadata
    is_upgrade: bool
    is_interactive: bool
    auto_yes: bool
    no_interactive: bool
    reconfigure: bool

    # Rule modules. A resolved ModuleSelection carrying the pre-check state, or
    # None when the checkout has no rules/ directory to offer.
    rule_selection: Any = None


@dataclass
class WizardResults:
    """Consolidated output from the upfront wizard.

    Every field has a sentinel value meaning "not asked / use default":

    - platforms: None means "not asked, use auto-detect".
      A list (even empty) means the user made an explicit selection.
    - profile_selection: None means "not asked / already configured".
      A slug string (e.g. "zen") means user picked a profile.
      Empty string "" means user explicitly chose "None" (no profile).
    - rule_modules: None means "not asked". A list (even empty) means the user
      made an explicit selection, and only then is anything written to
      ``rules.module.*``. This is what keeps a non-interactive install from
      recording a default as though it were the user's answer.
    """

    platforms: list[str] | None = None
    profile_selection: str | None = None
    rule_modules: list[str] | None = None
