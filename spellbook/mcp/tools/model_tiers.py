"""MCP tools for harness-scoped model tier routing.

These exist instead of telling agents to call ``spellbook_config_set`` with a
hand-built ``model.tier.<tier>.<harness>`` key. That tool validates nothing, so
a key assembled wrongly persists silently and reads back null forever. Here the
tier and harness are checked before anything is written.

The harness id is a PARAMETER rather than something the server detects. The
server genuinely cannot tell who is calling it: the ``X-Spellbook-Client``
header the hook stamps is never read, the HTTP transport is stateless, and
``prime_agent`` has no MCP client at all. The calling agent knows which harness
it is running in; the server does not.
"""

__all__ = [
    "spellbook_model_tier_resolve",
    "spellbook_model_tier_set",
    "spellbook_model_tier_status",
]

import logging

from spellbook.core.model_tiers import (
    TIER_GUIDANCE,
    TIERS,
    InvalidHarnessError,
    InvalidTierError,
    harnesses,
    resolve_tier_model,
    set_tier_model,
    unset_tiers_for,
)
from spellbook.mcp.server import mcp

logger = logging.getLogger(__name__)


@mcp.tool()
def spellbook_model_tier_status(harness: str) -> dict:
    """
    Report which model tiers have a recorded preference for a harness.

    Call this ONCE before dispatching subagents, not once per dispatch. If it
    reports unset tiers, ask the user which of the models YOU can actually see
    should map to each, then record them with spellbook_model_tier_set.

    Never invent a model id. Only offer models available in your own harness.

    Args:
        harness: The spellbook platform id you are running in, underscored --
            one of the ids listed in the "harnesses" field of the response.
            Note "claude_code", not "claude-code".

    Returns:
        {"harness":..., "tiers": {<tier>: {"model":..., "guidance":...}},
         "unset": [...], "harnesses": [...]}
        On a bad harness id: {"error": ...} listing the valid ids.
    """
    try:
        unset = unset_tiers_for(harness)
    except InvalidHarnessError as exc:
        return {"error": str(exc), "harnesses": list(harnesses())}
    return {
        "harness": harness,
        "tiers": {
            tier: {
                "model": resolve_tier_model(tier, harness),
                "guidance": TIER_GUIDANCE[tier],
            }
            for tier in TIERS
        },
        "unset": unset,
        "harnesses": list(harnesses()),
    }


@mcp.tool()
def spellbook_model_tier_resolve(tier: str, harness: str) -> dict:
    """
    Resolve one tier to the model recorded for it on a harness.

    A null model means NO PREFERENCE IS RECORDED. Treat that as "dispatch
    without a model override and let the harness use its own default" -- do
    not substitute a model of your own choosing.

    Args:
        tier: One of "heavy", "standard", "light".
        harness: The spellbook platform id you are running in, underscored.

    Returns:
        {"tier":..., "harness":..., "model": <str|null>, "guidance":...}
        On a bad tier or harness: {"error": ...}
    """
    try:
        model = resolve_tier_model(tier, harness)
    except (InvalidTierError, InvalidHarnessError) as exc:
        return {"error": str(exc), "tiers": list(TIERS), "harnesses": list(harnesses())}
    return {
        "tier": tier,
        "harness": harness,
        "model": model,
        "guidance": TIER_GUIDANCE[tier],
    }


@mcp.tool()
async def spellbook_model_tier_set(tier: str, harness: str, model: str) -> dict:
    """
    Record the model to use for a tier on a harness.

    Only call this with a model the USER chose. These are the user's
    preferences, and they persist across sessions -- writing a guess here is
    worse than leaving the tier unset, because unset falls back to the
    harness default while a wrong value silently routes every matching
    dispatch to the wrong model.

    Args:
        tier: One of "heavy", "standard", "light".
        harness: The spellbook platform id you are running in, underscored.
        model: The model identifier in the form YOUR harness expects. Spellbook
            does not validate this -- it cannot see your harness's model list.

    Returns:
        {"status": "ok", "key":..., "model":...}
        On a bad tier, harness, or empty model: {"error": ...}
    """
    try:
        set_tier_model(tier, harness, model)
    except (InvalidTierError, InvalidHarnessError, ValueError) as exc:
        return {"error": str(exc), "tiers": list(TIERS), "harnesses": list(harnesses())}
    return {
        "status": "ok",
        "key": f"model.tier.{tier}.{harness}",
        "model": model.strip(),
    }
