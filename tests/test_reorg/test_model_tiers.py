"""Tests for spellbook/core/model_tiers.py.

The module exists because ``config_set`` validates nothing, and these keys are
assembled at RUNTIME by an agent from parts it was told. So the tests that
matter most are the refusals: a typo'd tier or harness must raise rather than
persist a key that reads back None forever.

HOME is redirected on every test. ``tests/conftest.py`` fingerprints the real
``~/.config/spellbook/spellbook.json`` before and after each test and fails the
test that changed it -- these tests write config, so they must be isolated.
"""

import pytest

from spellbook.core import model_tiers


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Point the config resolver at a temp HOME.

    ``spellbook.core.compat.get_config_dir`` does NOT consult
    $SPELLBOOK_CONFIG_DIR (see its own warning), so HOME is the only lever
    that redirects config_get/config_set.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


# ---- key construction ----------------------------------------------------


def test_tier_key_shape():
    assert (
        model_tiers.tier_key("heavy", "claude_code")
        == "model.tier.heavy.claude_code"
    )


def test_every_tier_builds_a_key_for_every_harness():
    """No tier/harness pair may be unrepresentable -- a gap here would mean a
    harness that silently cannot record a preference."""
    for tier in model_tiers.TIERS:
        for harness in model_tiers.harnesses():
            assert model_tiers.tier_key(tier, harness).startswith(
                model_tiers.MODEL_TIER_KEY_PREFIX
            )


def test_unknown_tier_is_refused():
    with pytest.raises(model_tiers.InvalidTierError, match="unknown tier"):
        model_tiers.tier_key("medium", "claude_code")


def test_typo_in_tier_is_refused_not_persisted():
    """The failure this module exists to prevent: config_set would accept
    ``model.teir.heavy.claude_code`` silently and it would read back None
    forever, presenting as 'my preference is ignored'."""
    with pytest.raises(model_tiers.InvalidTierError):
        model_tiers.set_tier_model("heavey", "claude_code", "opus")


def test_unknown_harness_is_refused():
    with pytest.raises(model_tiers.InvalidHarnessError, match="unknown harness"):
        model_tiers.tier_key("heavy", "emacs")


def test_hyphenated_harness_id_is_refused():
    """The hook's runtime detector emits 'claude-code' while the installer's
    canonical id is 'claude_code'. Accepting both would split every user's
    preferences across two keys that never see each other."""
    with pytest.raises(model_tiers.InvalidHarnessError):
        model_tiers.tier_key("heavy", "claude-code")


# ---- resolution ----------------------------------------------------------


def test_unset_tier_resolves_to_none():
    """None means 'let the harness choose'. It must never be a model id
    spellbook invented, which would be wrong on most harnesses."""
    assert model_tiers.resolve_tier_model("heavy", "claude_code") is None


def test_set_then_resolve_round_trips():
    model_tiers.set_tier_model("heavy", "claude_code", "opus")
    assert model_tiers.resolve_tier_model("heavy", "claude_code") == "opus"


def test_preferences_are_scoped_per_harness():
    """The whole point: the same tier carries a different model per harness,
    and setting one must not disturb the other."""
    model_tiers.set_tier_model("heavy", "claude_code", "opus")
    model_tiers.set_tier_model("heavy", "prime_agent", "openrouter/minimax/minimax-m3")

    assert model_tiers.resolve_tier_model("heavy", "claude_code") == "opus"
    assert (
        model_tiers.resolve_tier_model("heavy", "prime_agent")
        == "openrouter/minimax/minimax-m3"
    )


def test_tiers_are_independent_within_a_harness():
    model_tiers.set_tier_model("heavy", "claude_code", "opus")
    assert model_tiers.resolve_tier_model("light", "claude_code") is None


def test_model_is_stripped():
    model_tiers.set_tier_model("light", "claude_code", "  haiku  ")
    assert model_tiers.resolve_tier_model("light", "claude_code") == "haiku"


def test_blank_model_is_refused():
    with pytest.raises(ValueError, match="non-empty string"):
        model_tiers.set_tier_model("light", "claude_code", "   ")


def test_non_string_value_written_out_of_band_reads_as_unset():
    """The raw config_set/CLI path can still write a non-string. Resolution
    must degrade to 'unset' rather than hand a dict to a dispatch call."""
    from spellbook.core.config import config_set

    config_set("model.tier.heavy.claude_code", {"not": "a model"})
    assert model_tiers.resolve_tier_model("heavy", "claude_code") is None


# ---- unset reporting -----------------------------------------------------


def test_unset_tiers_for_reports_all_when_fresh():
    assert model_tiers.unset_tiers_for("claude_code") == list(model_tiers.TIERS)


def test_unset_tiers_for_shrinks_as_preferences_land():
    model_tiers.set_tier_model("heavy", "claude_code", "opus")
    assert model_tiers.unset_tiers_for("claude_code") == ["standard", "light"]


def test_unset_tiers_for_is_harness_scoped():
    model_tiers.set_tier_model("heavy", "claude_code", "opus")
    assert model_tiers.unset_tiers_for("goose") == list(model_tiers.TIERS)


# ---- taxonomy invariants -------------------------------------------------


def test_tiers_are_ordered_heaviest_to_lightest():
    """Ordering is load-bearing: escalation goes UP a tier, never down."""
    assert model_tiers.TIERS == ("heavy", "standard", "light")


def test_every_tier_has_user_facing_guidance():
    """A tier with no guidance cannot be sensibly answered when the agent
    asks the user which model to map to it."""
    assert set(model_tiers.TIER_GUIDANCE) == set(model_tiers.TIERS)
    for tier, text in model_tiers.TIER_GUIDANCE.items():
        assert text.strip(), tier


def test_no_vendor_names_leak_into_the_shipped_taxonomy():
    """The repo-shipped tiers must stay generic. A vendor name here would
    recreate exactly the coupling this module removes."""
    blob = " ".join(model_tiers.TIER_GUIDANCE.values()).lower()
    for vendor in ("opus", "sonnet", "haiku", "claude", "gpt", "minimax", "deepseek", "openrouter"):
        assert vendor not in blob, f"{vendor!r} leaked into TIER_GUIDANCE"
