"""Task 6: CLI Flag Integration Tests.

Verify that CLI flags correctly influence wizard behavior by testing
the actual render_upfront_wizard() method with WizardContext fields
that correspond to each CLI flag.

These are NOT dataclass field assignment tests. Each test verifies
that the wizard's control flow changes: sections are skipped, defaults
are returned, or specific values propagate through.
"""

from __future__ import annotations

import pytest

from installer.wizard import WizardContext, WizardResults


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(**overrides) -> WizardContext:
    """Build a WizardContext with sensible defaults, applying overrides."""
    defaults = dict(
        available_platforms=["claude_code", "gemini"],
        cli_platforms=None,
        unset_security_keys=["security.crypto.enabled"],
        existing_config={},
        security_level=None,
        tts_disabled=False,
        tts_already_configured=False,
        profile_already_configured=False,
        available_profiles=[],
        is_upgrade=False,
        is_interactive=True,
        auto_yes=False,
        no_interactive=False,
        reconfigure=False,
    )
    defaults.update(overrides)
    return WizardContext(**defaults)


# ---------------------------------------------------------------------------
# Task 6a: --yes flag (auto_yes=True)
# ---------------------------------------------------------------------------


class TestYesFlagAutoYes:
    """--yes flag sets auto_yes=True, wizard returns defaults without prompting."""

    def test_auto_yes_returns_wizard_results_with_all_available_platforms(self):
        """auto_yes=True returns WizardResults with platforms=available_platforms."""
        from installer.renderer import PlainTextRenderer

        ctx = _make_ctx(auto_yes=True)
        renderer = PlainTextRenderer(auto_yes=True)
        result = renderer.render_upfront_wizard(ctx)

        assert result == WizardResults(
            platforms=["claude_code", "gemini"],
            security_selections=None,
            tts_intent=None,
            profile_selection=None,
        )

    def test_auto_yes_with_tts_disabled_returns_tts_intent_false(self):
        """auto_yes=True with tts_disabled=True returns tts_intent=False."""
        from installer.renderer import PlainTextRenderer

        ctx = _make_ctx(auto_yes=True, tts_disabled=True)
        renderer = PlainTextRenderer(auto_yes=True)
        result = renderer.render_upfront_wizard(ctx)

        assert result == WizardResults(
            platforms=["claude_code", "gemini"],
            security_selections=None,
            tts_intent=False,
            profile_selection=None,
        )

    def test_auto_yes_does_not_prompt_for_security(self, monkeypatch):
        """auto_yes=True does not call input() even with unset security keys."""
        from installer.renderer import PlainTextRenderer

        input_called = []
        monkeypatch.setattr("builtins.input", lambda _prompt: input_called.append(1) or "y")

        ctx = _make_ctx(
            auto_yes=True,
            unset_security_keys=["security.crypto.enabled"],
        )
        renderer = PlainTextRenderer(auto_yes=True)
        result = renderer.render_upfront_wizard(ctx)

        assert input_called == []
        assert result == WizardResults(
            platforms=["claude_code", "gemini"],
            security_selections=None,
            tts_intent=None,
            profile_selection=None,
        )


# ---------------------------------------------------------------------------
# Task 6b: --platforms flag (cli_platforms set)
# ---------------------------------------------------------------------------


class TestPlatformsFlag:
    """--platforms flag sets WizardContext.cli_platforms, skips platform selection."""

    def test_cli_platforms_used_in_auto_yes(self):
        """With cli_platforms and auto_yes, wizard uses cli_platforms not available."""
        from installer.renderer import PlainTextRenderer

        ctx = _make_ctx(cli_platforms=["gemini"], auto_yes=True)
        renderer = PlainTextRenderer(auto_yes=True)
        result = renderer.render_upfront_wizard(ctx)

        assert result == WizardResults(
            platforms=["gemini"],
            security_selections=None,
            tts_intent=None,
            profile_selection=None,
        )

    def test_cli_platforms_skips_interactive_select(self, monkeypatch):
        """With cli_platforms set, wizard does not prompt for platform selection."""
        from installer.renderer import PlainTextRenderer

        # Monkeypatch input to track if platform selection prompt happens
        input_prompts = []

        def tracking_input(prompt):
            input_prompts.append(prompt)
            return ""

        monkeypatch.setattr("builtins.input", tracking_input)

        ctx = _make_ctx(
            cli_platforms=["claude_code"],
            tts_already_configured=True,
        )
        renderer = PlainTextRenderer()
        result = renderer.render_upfront_wizard(ctx)

        assert result.platforms == ["claude_code"]
        # No platform selection prompt should have been shown.
        # The only possible input prompt is for security (crypto).
        # Platform selection uses "> " as prompt; security uses
        # something like "Enable ...". Verify no "> " prompt.
        assert not any(p == "> " for p in input_prompts)

    def test_cli_platforms_single_platform(self):
        """Single platform from CLI flag is used directly."""
        from installer.renderer import PlainTextRenderer

        ctx = _make_ctx(cli_platforms=["opencode"], auto_yes=True)
        renderer = PlainTextRenderer(auto_yes=True)
        result = renderer.render_upfront_wizard(ctx)

        assert result.platforms == ["opencode"]


# ---------------------------------------------------------------------------
# Task 6c: --security-level flag (security_level set)
# ---------------------------------------------------------------------------


class TestSecurityLevelFlag:
    """--security-level flag sets security_level, skips security questions."""

    def test_security_level_set_skips_security_section(self):
        """When security_level is set, security_selections remains None."""
        from installer.renderer import PlainTextRenderer

        ctx = _make_ctx(
            security_level="standard",
            unset_security_keys=["security.crypto.enabled", "security.sleuth.enabled"],
            auto_yes=True,
        )
        renderer = PlainTextRenderer(auto_yes=True)
        result = renderer.render_upfront_wizard(ctx)

        assert result.security_selections is None

    def test_security_level_does_not_prompt(self, monkeypatch):
        """When security_level is set, no security prompts appear."""
        from installer.renderer import PlainTextRenderer

        input_called = []
        monkeypatch.setattr("builtins.input", lambda _prompt: input_called.append(1) or "y")

        ctx = _make_ctx(
            security_level="strict",
            unset_security_keys=["security.crypto.enabled"],
            tts_already_configured=True,
            cli_platforms=["claude_code"],
        )
        renderer = PlainTextRenderer()
        result = renderer.render_upfront_wizard(ctx)

        # No input calls should happen: cli_platforms skips platform prompt,
        # security_level skips security prompt, tts_already_configured skips TTS
        assert input_called == []
        assert result.security_selections is None

    def test_no_security_level_with_unset_keys_prompts(self, monkeypatch):
        """Without security_level, unset keys trigger security prompts."""
        from installer.renderer import PlainTextRenderer

        security_prompts = []

        def tracking_input(prompt):
            security_prompts.append(prompt)
            return "y"

        monkeypatch.setattr("builtins.input", tracking_input)

        ctx = _make_ctx(
            security_level=None,
            unset_security_keys=["security.crypto.enabled"],
            cli_platforms=["claude_code"],
            tts_already_configured=True,
        )
        renderer = PlainTextRenderer()
        result = renderer.render_upfront_wizard(ctx)

        # Security section should have prompted for crypto
        assert len(security_prompts) >= 1
        assert result.security_selections is not None


# ---------------------------------------------------------------------------
# Task 6d: --no-tts flag (tts_disabled=True)
# ---------------------------------------------------------------------------


class TestNoTTSFlag:
    """--no-tts flag sets tts_disabled=True, tts_intent=False in results."""

    def test_tts_disabled_sets_intent_false_in_auto_yes(self):
        """tts_disabled=True with auto_yes sets tts_intent=False."""
        from installer.renderer import PlainTextRenderer

        ctx = _make_ctx(tts_disabled=True, auto_yes=True)
        renderer = PlainTextRenderer(auto_yes=True)
        result = renderer.render_upfront_wizard(ctx)

        assert result.tts_intent is False

    def test_tts_disabled_sets_intent_false_in_interactive(self, monkeypatch):
        """tts_disabled=True sets tts_intent=False even in interactive mode."""
        from installer.renderer import PlainTextRenderer

        # Should not prompt for TTS at all
        input_prompts = []
        monkeypatch.setattr("builtins.input", lambda p: input_prompts.append(p) or "")

        ctx = _make_ctx(
            tts_disabled=True,
            cli_platforms=["claude_code"],
            unset_security_keys=[],
        )
        renderer = PlainTextRenderer()
        result = renderer.render_upfront_wizard(ctx)

        assert result.tts_intent is False
        # No TTS prompt should appear
        assert not any("TTS" in p for p in input_prompts)

    def test_tts_not_disabled_and_not_configured_prompts(self, monkeypatch):
        """Without --no-tts and not already configured, TTS prompt appears."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "n")

        ctx = _make_ctx(
            tts_disabled=False,
            tts_already_configured=False,
            cli_platforms=["claude_code"],
            unset_security_keys=[],
        )
        renderer = PlainTextRenderer()
        result = renderer.render_upfront_wizard(ctx)

        assert result.tts_intent is False


# ---------------------------------------------------------------------------
# Task 6e: --no-interactive flag (no_interactive=True)
# ---------------------------------------------------------------------------


class TestNoInteractiveFlag:
    """--no-interactive sets no_interactive=True, platform selection skipped."""

    def test_no_interactive_auto_selects_all_platforms(self):
        """no_interactive=True auto-selects all available platforms."""
        from installer.renderer import PlainTextRenderer

        ctx = _make_ctx(
            no_interactive=True,
            unset_security_keys=[],
            tts_already_configured=True,
        )
        renderer = PlainTextRenderer()
        result = renderer.render_upfront_wizard(ctx)

        assert result.platforms == ["claude_code", "gemini"]

    def test_no_interactive_does_not_prompt_for_platforms(self, monkeypatch):
        """no_interactive=True skips platform selection prompt entirely."""
        from installer.renderer import PlainTextRenderer

        input_prompts = []
        monkeypatch.setattr("builtins.input", lambda p: input_prompts.append(p) or "")

        ctx = _make_ctx(
            no_interactive=True,
            unset_security_keys=[],
            tts_already_configured=True,
        )
        renderer = PlainTextRenderer()
        result = renderer.render_upfront_wizard(ctx)

        assert result.platforms == ["claude_code", "gemini"]
        # No "> " prompt (platform selection) should appear
        assert not any(p == "> " for p in input_prompts)

    def test_no_interactive_still_uses_cli_platforms_if_provided(self):
        """CLI platforms take priority over no_interactive auto-select."""
        from installer.renderer import PlainTextRenderer

        ctx = _make_ctx(
            no_interactive=True,
            cli_platforms=["gemini"],
            auto_yes=True,
        )
        renderer = PlainTextRenderer(auto_yes=True)
        result = renderer.render_upfront_wizard(ctx)

        assert result.platforms == ["gemini"]


# ---------------------------------------------------------------------------
# Task 6f: Combined flag interactions
# ---------------------------------------------------------------------------


class TestCombinedFlags:
    """Verify that multiple flags combine correctly."""

    def test_yes_with_platforms_and_no_tts(self):
        """--yes --platforms=gemini --no-tts: all three flags applied."""
        from installer.renderer import PlainTextRenderer

        ctx = _make_ctx(
            auto_yes=True,
            cli_platforms=["gemini"],
            tts_disabled=True,
        )
        renderer = PlainTextRenderer(auto_yes=True)
        result = renderer.render_upfront_wizard(ctx)

        assert result == WizardResults(
            platforms=["gemini"],
            security_selections=None,
            tts_intent=False,
            profile_selection=None,
        )

    def test_no_interactive_with_security_level_and_no_tts(self, monkeypatch):
        """--no-interactive --security-level=minimal --no-tts: no prompts at all."""
        from installer.renderer import PlainTextRenderer

        input_called = []
        monkeypatch.setattr("builtins.input", lambda _p: input_called.append(1) or "")

        ctx = _make_ctx(
            no_interactive=True,
            security_level="minimal",
            tts_disabled=True,
            unset_security_keys=["security.crypto.enabled"],
            tts_already_configured=False,
        )
        renderer = PlainTextRenderer()
        result = renderer.render_upfront_wizard(ctx)

        assert input_called == []
        assert result == WizardResults(
            platforms=["claude_code", "gemini"],
            security_selections=None,
            tts_intent=False,
            profile_selection=None,
        )
