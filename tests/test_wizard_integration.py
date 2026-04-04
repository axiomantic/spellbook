"""Task 9: End-to-End Integration Tests for the wizard-first flow.

Verifies the full wizard-first installation flow end-to-end:
1. Fresh install: wizard collects all answers, install runs with collected values
2. Upgrade flow: wizard skips already-configured items
3. Wizard cancel (None return): exits with code 1
4. Dry-run mode: wizard runs but install is dry-run
5. Security key conversion: dotted keys from wizard become bare IDs for Installer.run()
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from installer.wizard import WizardContext, WizardResults


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_args(**overrides) -> argparse.Namespace:
    """Build a minimal argparse.Namespace matching install.py's main() output."""
    defaults = dict(
        yes=False,
        install_dir=None,
        platforms=None,
        force=False,
        dry_run=True,
        no_interactive=False,
        no_admin=False,
        update_only=False,
        bootstrapped=True,
        security_level=None,
        no_tts=False,
        reconfigure=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_session(**overrides) -> SimpleNamespace:
    """Build a fake InstallSession result from Installer.run()."""
    defaults = dict(
        success=True,
        dry_run=True,
        platforms_installed=["claude_code"],
        platforms_failed=[],
        previous_version=None,
        version="0.1.0",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _spellbook_dir() -> Path:
    """Get the real spellbook directory (repo root)."""
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 9a: Fresh install flow
# ---------------------------------------------------------------------------


class TestFreshInstallFlow:
    """Fresh install: wizard collects all answers, install runs with them."""

    def test_fresh_install_wizard_collects_and_passes_platforms(self, monkeypatch):
        """Fresh install: wizard returns platforms, passed to Installer.run()."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=True)

        run_call_kwargs = {}

        def fake_render_upfront_wizard(self, ctx):
            return WizardResults(
                platforms=["claude_code", "gemini"],
                security_selections={
                    "security.crypto.enabled": True,
                    "security.sleuth.enabled": False,
                },
                tts_intent=True,
                profile_selection="zen",
            )

        def fake_installer_run(self, **kwargs):
            run_call_kwargs.update(kwargs)
            return _make_session()

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(
            "installer.core.Installer.run",
            fake_installer_run,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

        from install import run_installation

        result = run_installation(spellbook_dir, args)

        assert result == 0
        assert run_call_kwargs["platforms"] == ["claude_code", "gemini"]
        assert run_call_kwargs["dry_run"] is True

    def test_fresh_install_security_selections_converted_and_passed(self, monkeypatch):
        """Fresh install: dotted security keys converted to bare IDs for Installer.run()."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=True)

        run_call_kwargs = {}

        def fake_render_upfront_wizard(self, ctx):
            return WizardResults(
                platforms=["claude_code"],
                security_selections={
                    "security.crypto.enabled": True,
                    "security.sleuth.enabled": False,
                },
            )

        def fake_installer_run(self, **kwargs):
            run_call_kwargs.update(kwargs)
            return _make_session()

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(
            "installer.core.Installer.run",
            fake_installer_run,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

        from install import run_installation

        run_installation(spellbook_dir, args)

        assert run_call_kwargs["security_selections"] == {
            "crypto": True,
            "sleuth": False,
        }

    def test_fresh_install_tts_intent_true_triggers_setup(self, monkeypatch):
        """Fresh install: tts_intent=True triggers TTS setup after install."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=False)

        set_tts_calls = []

        def fake_render_upfront_wizard(self, ctx):
            return WizardResults(
                platforms=["claude_code"],
                tts_intent=True,
            )

        def fake_installer_run(self, **kwargs):
            return _make_session(dry_run=False)

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(
            "installer.core.Installer.run",
            fake_installer_run,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
        monkeypatch.setattr("install.check_tts_available", lambda: True)
        monkeypatch.setattr(
            "install._set_tts_config",
            lambda enabled: set_tts_calls.append(enabled),
        )
        monkeypatch.setattr("install.show_admin_info", lambda enabled: None)
        monkeypatch.setattr("install.show_whats_new", lambda *a: None)

        from install import run_installation

        run_installation(spellbook_dir, args)

        assert set_tts_calls == [True]

    def test_fresh_install_profile_selection_applied(self, monkeypatch):
        """Fresh install: profile_selection='zen' applied via config_set."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=False)

        config_set_calls = []

        def fake_render_upfront_wizard(self, ctx):
            return WizardResults(
                platforms=["claude_code"],
                profile_selection="zen",
            )

        def fake_installer_run(self, **kwargs):
            return _make_session(dry_run=False)

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(
            "installer.core.Installer.run",
            fake_installer_run,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
        monkeypatch.setattr(
            "spellbook.core.config.config_set",
            lambda key, value: config_set_calls.append((key, value)),
        )
        monkeypatch.setattr("install._set_tts_config", lambda enabled: None)
        monkeypatch.setattr("install.show_admin_info", lambda enabled: None)
        monkeypatch.setattr("install.show_whats_new", lambda *a: None)

        from install import run_installation

        run_installation(spellbook_dir, args)

        profile_calls = [c for c in config_set_calls if c[0] == "profile.default"]
        assert profile_calls == [("profile.default", "zen")]


# ---------------------------------------------------------------------------
# 9b: Upgrade flow - wizard skips already-configured items
# ---------------------------------------------------------------------------


class TestUpgradeFlow:
    """Upgrade flow: wizard skips already-configured items."""

    def test_upgrade_tts_already_configured_skipped(self):
        """When tts_already_configured=True, wizard does not prompt for TTS."""
        from installer.renderer import PlainTextRenderer

        ctx = WizardContext(
            available_platforms=["claude_code"],
            cli_platforms=["claude_code"],
            unset_security_keys=[],
            existing_config={},
            security_level=None,
            tts_disabled=False,
            tts_already_configured=True,
            profile_already_configured=False,
            available_profiles=[],
            is_upgrade=True,
            is_interactive=True,
            auto_yes=True,
            no_interactive=False,
            reconfigure=False,
        )
        renderer = PlainTextRenderer(auto_yes=True)
        result = renderer.render_upfront_wizard(ctx)

        assert result == WizardResults(
            platforms=["claude_code"],
            security_selections=None,
            tts_intent=None,
            profile_selection=None,
        )

    def test_upgrade_profile_already_configured_skipped(self, monkeypatch):
        """When profile_already_configured=True, wizard does not ask for profile."""
        from installer.renderer import PlainTextRenderer

        input_calls = []
        monkeypatch.setattr("builtins.input", lambda p: input_calls.append(p) or "")

        ctx = WizardContext(
            available_platforms=["claude_code"],
            cli_platforms=["claude_code"],
            unset_security_keys=[],
            existing_config={},
            security_level=None,
            tts_disabled=False,
            tts_already_configured=True,
            profile_already_configured=True,
            available_profiles=["zen", "default"],
            is_upgrade=True,
            is_interactive=True,
            auto_yes=False,
            no_interactive=False,
            reconfigure=False,
        )
        renderer = PlainTextRenderer()
        result = renderer.render_upfront_wizard(ctx)

        # No input prompts at all: cli_platforms skips platform, no unset security,
        # tts configured, profile configured
        assert input_calls == []
        assert result == WizardResults(
            platforms=["claude_code"],
            security_selections=None,
            tts_intent=None,
            profile_selection=None,
        )

    def test_upgrade_no_unset_security_keys_skips_security(self):
        """When all security keys are set (empty unset list), security section skipped."""
        from installer.renderer import PlainTextRenderer

        ctx = WizardContext(
            available_platforms=["claude_code"],
            cli_platforms=None,
            unset_security_keys=[],
            existing_config={"security.crypto.enabled": True},
            security_level=None,
            tts_disabled=False,
            tts_already_configured=True,
            profile_already_configured=True,
            available_profiles=[],
            is_upgrade=True,
            is_interactive=True,
            auto_yes=True,
            no_interactive=False,
            reconfigure=False,
        )
        renderer = PlainTextRenderer(auto_yes=True)
        result = renderer.render_upfront_wizard(ctx)

        assert result.security_selections is None


# ---------------------------------------------------------------------------
# 9c: Wizard cancel (None return) -> exit code 1
# ---------------------------------------------------------------------------


class TestWizardCancelExitsWithCode1:
    """Wizard returning None (user cancelled) causes exit code 1."""

    def test_wizard_none_returns_exit_code_1(self, monkeypatch):
        """render_upfront_wizard returning None causes run_installation to return 1."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=False, dry_run=True)

        def fake_render_upfront_wizard(self, ctx):
            return None

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

        from install import run_installation

        result = run_installation(spellbook_dir, args)

        assert result == 1

    def test_wizard_cancel_does_not_call_installer_run(self, monkeypatch):
        """When wizard is cancelled, Installer.run() is never called."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=False, dry_run=True)

        installer_run_called = []

        def fake_render_upfront_wizard(self, ctx):
            return None

        def fake_installer_run(self, **kwargs):
            installer_run_called.append(True)
            return _make_session()

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(
            "installer.core.Installer.run",
            fake_installer_run,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

        from install import run_installation

        run_installation(spellbook_dir, args)

        assert installer_run_called == []


# ---------------------------------------------------------------------------
# 9d: Dry-run mode
# ---------------------------------------------------------------------------


class TestDryRunMode:
    """Dry-run: wizard runs normally, install uses dry_run=True."""

    def test_dry_run_wizard_runs_normally(self, monkeypatch):
        """In dry-run mode, wizard still collects answers."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=True)

        wizard_called = []

        def fake_render_upfront_wizard(self, ctx):
            wizard_called.append(ctx)
            return WizardResults(platforms=["claude_code"])

        def fake_installer_run(self, **kwargs):
            return _make_session(dry_run=True)

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(
            "installer.core.Installer.run",
            fake_installer_run,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

        from install import run_installation

        result = run_installation(spellbook_dir, args)

        assert result == 0
        assert len(wizard_called) == 1

    def test_dry_run_passes_dry_run_to_installer(self, monkeypatch):
        """In dry-run mode, Installer.run() receives dry_run=True."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=True)

        run_call_kwargs = {}

        def fake_render_upfront_wizard(self, ctx):
            return WizardResults(platforms=["claude_code"])

        def fake_installer_run(self, **kwargs):
            run_call_kwargs.update(kwargs)
            return _make_session(dry_run=True)

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(
            "installer.core.Installer.run",
            fake_installer_run,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

        from install import run_installation

        run_installation(spellbook_dir, args)

        assert run_call_kwargs["dry_run"] is True

    def test_dry_run_does_not_apply_profile(self, monkeypatch):
        """In dry-run mode, profile_selection is NOT applied via config_set."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=True)

        config_set_calls = []

        def fake_render_upfront_wizard(self, ctx):
            return WizardResults(
                platforms=["claude_code"],
                profile_selection="zen",
            )

        def fake_installer_run(self, **kwargs):
            return _make_session(dry_run=True)

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(
            "installer.core.Installer.run",
            fake_installer_run,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
        monkeypatch.setattr(
            "spellbook.core.config.config_set",
            lambda key, value: config_set_calls.append((key, value)),
        )

        from install import run_installation

        run_installation(spellbook_dir, args)

        # Profile should NOT be applied in dry-run mode
        profile_calls = [c for c in config_set_calls if c[0] == "profile.default"]
        assert profile_calls == []


# ---------------------------------------------------------------------------
# 9e: Security key conversion
# ---------------------------------------------------------------------------


class TestSecurityKeyConversion:
    """Dotted keys from wizard become bare IDs for Installer.run()."""

    def test_standard_dotted_key_conversion(self):
        """security.crypto.enabled -> crypto, security.sleuth.enabled -> sleuth."""
        wizard_selections = {
            "security.crypto.enabled": True,
            "security.sleuth.enabled": False,
            "security.spotlighting.enabled": True,
            "security.lodo.enabled": False,
        }

        bare = {}
        for dotted_key, value in wizard_selections.items():
            parts = dotted_key.split(".")
            if len(parts) >= 2:
                bare[parts[1]] = value
            else:
                bare[dotted_key] = value

        assert bare == {
            "crypto": True,
            "sleuth": False,
            "spotlighting": True,
            "lodo": False,
        }

    def test_bare_key_passthrough(self):
        """Keys without dots pass through unchanged."""
        wizard_selections = {"crypto": True}

        bare = {}
        for dotted_key, value in wizard_selections.items():
            parts = dotted_key.split(".")
            if len(parts) >= 2:
                bare[parts[1]] = value
            else:
                bare[dotted_key] = value

        assert bare == {"crypto": True}

    def test_conversion_in_run_installation(self, monkeypatch):
        """run_installation() converts dotted wizard keys to bare IDs before Installer.run()."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=True)

        run_call_kwargs = {}

        def fake_render_upfront_wizard(self, ctx):
            return WizardResults(
                platforms=["claude_code"],
                security_selections={
                    "security.crypto.enabled": True,
                    "security.sleuth.enabled": False,
                    "security.spotlighting.enabled": True,
                    "security.lodo.enabled": False,
                },
            )

        def fake_installer_run(self, **kwargs):
            run_call_kwargs.update(kwargs)
            return _make_session()

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(
            "installer.core.Installer.run",
            fake_installer_run,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

        from install import run_installation

        run_installation(spellbook_dir, args)

        assert run_call_kwargs["security_selections"] == {
            "crypto": True,
            "sleuth": False,
            "spotlighting": True,
            "lodo": False,
        }

    def test_security_level_flag_overrides_wizard_selections(self, monkeypatch):
        """--security-level flag takes priority over wizard security_selections."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=True, security_level="standard")

        run_call_kwargs = {}

        def fake_render_upfront_wizard(self, ctx):
            # Wizard returns None for security_selections when security_level is set
            return WizardResults(
                platforms=["claude_code"],
                security_selections=None,
            )

        def fake_installer_run(self, **kwargs):
            run_call_kwargs.update(kwargs)
            return _make_session()

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(
            "installer.core.Installer.run",
            fake_installer_run,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

        from install import run_installation

        run_installation(spellbook_dir, args)

        # security_level_to_selections("standard") produces these values
        assert run_call_kwargs["security_selections"] == {
            "spotlighting": True,
            "crypto": True,
            "sleuth": False,
            "lodo": False,
        }

    def test_empty_security_selections_passes_none(self, monkeypatch):
        """When wizard returns security_selections=None, Installer.run() gets None."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=True)

        run_call_kwargs = {}

        def fake_render_upfront_wizard(self, ctx):
            return WizardResults(
                platforms=["claude_code"],
                security_selections=None,
            )

        def fake_installer_run(self, **kwargs):
            run_call_kwargs.update(kwargs)
            return _make_session()

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(
            "installer.core.Installer.run",
            fake_installer_run,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

        from install import run_installation

        run_installation(spellbook_dir, args)

        assert run_call_kwargs["security_selections"] is None
