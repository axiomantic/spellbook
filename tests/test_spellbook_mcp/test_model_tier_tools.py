"""Tests for the model-tier MCP tools.

The core module (`spellbook/core/model_tiers.py`) raises on a bad tier or
harness; these tools must translate that into an error DICT instead, because an
MCP tool that raises surfaces to the calling agent as a transport failure with
no usable guidance. The translation is the entire value of these wrappers, so
it is what gets tested here: every refusal path returns a dict, and every
refusal dict carries the valid values the agent needs to retry.

`@mcp.tool()` returns the plain function, so the tools are called directly.
HOME is redirected because `tests/conftest.py` fails any test that mutates the
real `~/.config/spellbook/spellbook.json`.
"""

import pytest

from spellbook.core import model_tiers as core
from spellbook.mcp.tools.model_tiers import (
    spellbook_model_tier_resolve,
    spellbook_model_tier_set,
    spellbook_model_tier_status,
)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect config on every platform.

    APPDATA is the Windows lever -- ``get_config_dir`` reads it there rather
    than HOME, so redirecting only HOME/USERPROFILE leaves Windows writing to
    the real user config and leaking state between tests.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return tmp_path


# ---- status --------------------------------------------------------------


def test_status_on_fresh_config_reports_every_tier_unset():
    result = spellbook_model_tier_status("claude_code")

    assert result["harness"] == "claude_code"
    assert result["unset"] == list(core.TIERS)
    assert set(result["tiers"]) == set(core.TIERS)
    assert all(t["model"] is None for t in result["tiers"].values())


def test_status_carries_guidance_for_every_tier():
    """The agent shows this to the user when asking which model to map. A tier
    with no guidance cannot be sensibly answered."""
    result = spellbook_model_tier_status("claude_code")
    for tier in core.TIERS:
        assert result["tiers"][tier]["guidance"].strip()


def test_status_reflects_recorded_preferences():
    core.set_tier_model("heavy", "claude_code", "opus")

    result = spellbook_model_tier_status("claude_code")

    assert result["tiers"]["heavy"]["model"] == "opus"
    assert result["unset"] == ["standard", "light"]


def test_status_is_harness_scoped():
    core.set_tier_model("heavy", "claude_code", "opus")

    assert spellbook_model_tier_status("goose")["unset"] == list(core.TIERS)


def test_status_rejects_unknown_harness_without_raising():
    result = spellbook_model_tier_status("emacs")

    assert "error" in result
    assert "claude_code" in result["harnesses"]
    assert "tiers" not in result


def test_status_rejects_hyphenated_harness_id():
    """The hook's detector emits 'claude-code'; the installer's canonical id is
    'claude_code'. Accepting both would split preferences across two keys."""
    assert "error" in spellbook_model_tier_status("claude-code")


# ---- resolve -------------------------------------------------------------


def test_resolve_unset_returns_null_model_not_an_error():
    """Null means 'dispatch without an override'. An unset tier is a normal
    state, not a failure -- treating it as an error would block dispatches in
    non-interactive runs."""
    result = spellbook_model_tier_resolve("heavy", "claude_code")

    assert result["model"] is None
    assert "error" not in result


def test_resolve_returns_recorded_model():
    core.set_tier_model("light", "prime_agent", "openrouter/deepseek/deepseek-v4-flash-0731")

    result = spellbook_model_tier_resolve("light", "prime_agent")

    assert result["model"] == "openrouter/deepseek/deepseek-v4-flash-0731"
    assert result["tier"] == "light"
    assert result["harness"] == "prime_agent"


def test_resolve_rejects_unknown_tier_and_lists_valid_ones():
    result = spellbook_model_tier_resolve("medium", "claude_code")

    assert "error" in result
    assert result["tiers"] == list(core.TIERS)


def test_resolve_rejects_unknown_harness():
    assert "error" in spellbook_model_tier_resolve("heavy", "emacs")


# ---- set -----------------------------------------------------------------


async def test_set_records_and_reports_the_key():
    result = await spellbook_model_tier_set("heavy", "claude_code", "opus")

    assert result["status"] == "ok"
    assert result["key"] == "model.tier.heavy.claude_code"
    assert core.resolve_tier_model("heavy", "claude_code") == "opus"


async def test_set_strips_whitespace():
    result = await spellbook_model_tier_set("light", "claude_code", "  haiku  ")

    assert result["model"] == "haiku"
    assert core.resolve_tier_model("light", "claude_code") == "haiku"


async def test_set_rejects_unknown_tier_without_raising():
    result = await spellbook_model_tier_set("heavey", "claude_code", "opus")

    assert "error" in result
    assert result["tiers"] == list(core.TIERS)


async def test_set_rejects_unknown_harness_without_raising():
    result = await spellbook_model_tier_set("heavy", "emacs", "opus")

    assert "error" in result
    assert "claude_code" in result["harnesses"]


async def test_set_rejects_empty_model():
    result = await spellbook_model_tier_set("heavy", "claude_code", "   ")

    assert "error" in result


async def test_a_refused_set_persists_nothing():
    """The refusal must be total. A wrapper that reported an error but had
    already written would leave the user with a preference they were told was
    rejected -- worse than either outcome alone."""
    await spellbook_model_tier_set("heavy", "claude-code", "opus")
    await spellbook_model_tier_set("heavey", "claude_code", "opus")
    await spellbook_model_tier_set("heavy", "claude_code", "")

    assert core.resolve_tier_model("heavy", "claude_code") is None
    assert spellbook_model_tier_status("claude_code")["unset"] == list(core.TIERS)


async def test_set_then_resolve_round_trips_through_the_tools():
    """End to end across all three tools, which is how an agent uses them."""
    assert "heavy" in spellbook_model_tier_status("goose")["unset"]

    await spellbook_model_tier_set("heavy", "goose", "some-model")

    assert spellbook_model_tier_resolve("heavy", "goose")["model"] == "some-model"
    assert "heavy" not in spellbook_model_tier_status("goose")["unset"]
