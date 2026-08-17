"""Harness-scoped model routing by generic tier.

Spellbook installs to nine harnesses. A model slug that is correct in one is
meaningless in another -- ``openrouter/minimax/minimax-m3`` does nothing on
Claude Code, and ``opus`` does nothing on a harness wired to OpenRouter. So a
single repo-wide routing table cannot be right; it can only be right for
whoever wrote it.

What the repo ships is therefore GENERIC: three tiers naming the SHAPE of the
work, with no vendor in them.

    heavy     -- reasoning-dominant work where a wrong answer is expensive to
                 discover later: code review, conflict synthesis, design
                 critique, research synthesis.
    standard  -- judgement work with a bounded blast radius: monitoring,
                 scope assessment, integration review.
    light     -- mechanical work with a checkable result: applying a known
                 edit, running a test command, git and PR plumbing.

What each tier MEANS on a given harness is user-specific and harness-specific,
so it lives in the user's config under::

    model.tier.<tier>.<harness>

Nothing here guesses a value. An unset tier resolves to ``None``, which means
"let the harness use its own default" -- never a fabricated model id.

## Why validation lives here

``config_set`` applies no validation of any kind: any key, any value. A typo
like ``model.teir.heavy.claude_code`` persists silently and reads back
``None`` forever, which presents as "the preference I set is being ignored"
with nothing to grep for. Since these keys are written at RUNTIME by an agent
assembling the key from parts, that is a likely failure rather than a
theoretical one. ``tier_key`` is the only supported way to build one, and it
refuses both halves it can check.
"""

from __future__ import annotations

from spellbook.core.config import config_get, config_set

__all__ = [
    "MODEL_TIER_KEY_PREFIX",
    "TIERS",
    "TIER_GUIDANCE",
    "InvalidHarnessError",
    "InvalidTierError",
    "harnesses",
    "resolve_tier_model",
    "set_tier_model",
    "tier_key",
    "unset_tiers_for",
]

# Ordered heaviest to lightest. Ordering is meaningful: escalation goes UP a
# tier, never down -- a task that outgrew its tier needs more capability, and
# silently giving it less is how a cheap model gets handed the one job that
# actually mattered.
TIERS: tuple[str, ...] = ("heavy", "standard", "light")

MODEL_TIER_KEY_PREFIX = "model.tier."

# Shown to the user when asking them to pick a model for a tier. Kept here
# rather than in the prompt text so the CLI, the MCP tool, and the rules all
# describe a tier the same way.
TIER_GUIDANCE: dict[str, str] = {
    "heavy": (
        "Reasoning-dominant work where a wrong answer is expensive to discover "
        "later: code review, conflict synthesis, design critique, research "
        "synthesis. Prefer your most capable available model."
    ),
    "standard": (
        "Judgement work with a bounded blast radius: monitoring, scope "
        "assessment, integration review. Prefer a mid-capability model."
    ),
    "light": (
        "Mechanical work with a checkable result: applying a known edit, "
        "running a test command, git and PR plumbing. Prefer your cheapest "
        "and fastest available model."
    ),
}


class InvalidTierError(ValueError):
    """The tier is not one of ``TIERS``."""


class InvalidHarnessError(ValueError):
    """The harness is not a supported platform id."""


def harnesses() -> tuple[str, ...]:
    """Supported harness ids, as the installer defines them.

    Imported lazily and deliberately. ``installer`` is not a dependency of the
    ``spellbook`` package at import time, and this module is reachable from
    ``spellbook.core.config`` consumers, which would otherwise pay the installer
    import whether or not a tier key is ever built. Resolving the list only on
    demand keeps that path free.
    """
    from installer.config import SUPPORTED_PLATFORMS

    return tuple(SUPPORTED_PLATFORMS)


def tier_key(tier: str, harness: str) -> str:
    """Build the config key for ``tier`` on ``harness``, validating both.

    This is the ONLY supported way to construct one of these keys. Building
    the string by hand bypasses the checks and, because ``config_set`` accepts
    anything, a mistake is silent and permanent.
    """
    if tier not in TIERS:
        raise InvalidTierError(
            f"unknown tier {tier!r}; valid tiers are {list(TIERS)}"
        )
    known = harnesses()
    if harness not in known:
        raise InvalidHarnessError(
            f"unknown harness {harness!r}; valid harnesses are {list(known)}. "
            "Use the installer's platform id (underscored), not the hook's "
            "hyphenated client string."
        )
    return f"{MODEL_TIER_KEY_PREFIX}{tier}.{harness}"


def resolve_tier_model(tier: str, harness: str) -> str | None:
    """The model recorded for ``tier`` on ``harness``, or ``None`` if unset.

    ``None`` means "no preference recorded" and MUST be treated as "let the
    harness pick its own default". It never means "use some fallback model
    spellbook chose", because any model spellbook could name here would be
    wrong on most harnesses -- which is the whole reason this module exists.
    """
    value = config_get(tier_key(tier, harness))
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        # A non-string or blank landed here through the unvalidated
        # config_set/CLI path. Treat it as unset rather than handing a
        # dict or an empty string to a dispatch call.
        return None
    return value.strip()


def set_tier_model(tier: str, harness: str, model: str) -> dict:
    """Record ``model`` for ``tier`` on ``harness``.

    ``model`` is deliberately NOT validated against a list of known models:
    the set of valid models is a property of the user's harness and account,
    which spellbook cannot see. The tier and harness are checkable, so those
    are checked; the model is the user's word.
    """
    if not isinstance(model, str) or not model.strip():
        raise ValueError(
            f"model must be a non-empty string, got {model!r}. To clear a "
            "preference, use unset_tiers_for or edit spellbook.json directly."
        )
    return config_set(tier_key(tier, harness), model.strip())


def unset_tiers_for(harness: str) -> list[str]:
    """Return the tiers on ``harness`` that have no recorded model.

    Ordered heaviest to lightest, matching ``TIERS``. An agent uses this to
    ask about everything it still needs in ONE exchange rather than
    interrupting once per dispatch.
    """
    return [t for t in TIERS if resolve_tier_model(t, harness) is None]
