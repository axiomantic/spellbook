"""Tests for run_installation() wizard-first flow (Task 5).

Verifies that run_installation() correctly:
1. Assembles WizardContext from CLI args and existing config state
2. Calls renderer.render_upfront_wizard(context) to collect answers
3. Extracts platforms, security_selections, tts_intent, profile from results
4. Passes platforms and security_selections to Installer.run()
5. Handles wizard cancellation (returns None -> exit code 1)
6. Applies profile selection immediately
7. Drives post-install TTS config from tts_intent
8. Preserves --reconfigure path (unchanged)
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
        security_wizard=False,
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
# Test: wizard cancellation -> exit code 1
# ---------------------------------------------------------------------------


class TestWizardCancellationExitsWithCode1:
    """When wizard returns None (user cancelled), run_installation returns 1."""

    def test_wizard_returns_none_exits_1(self, monkeypatch):
        """render_upfront_wizard returning None causes exit code 1."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=False, dry_run=True)

        # Track calls
        upfront_wizard_called = []

        def fake_render_upfront_wizard(self, ctx):
            upfront_wizard_called.append(ctx)
            return None  # user cancelled

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

        from install import run_installation

        result = run_installation(spellbook_dir, args)

        assert result == 1
        assert len(upfront_wizard_called) == 1


# ---------------------------------------------------------------------------
# Test: wizard_results.platforms passed to Installer.run()
# ---------------------------------------------------------------------------


class TestWizardPlatformsPassedToInstallerRun:
    """Platforms from wizard results are passed to Installer.run()."""

    def test_wizard_platforms_passed_to_installer(self, monkeypatch):
        """Platforms from WizardResults are passed as the platforms arg to Installer.run()."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=True)

        run_call_kwargs = {}

        def fake_render_upfront_wizard(self, ctx):
            return WizardResults(
                platforms=["gemini"],
                security_selections=None,
                tts_intent=None,
                profile_selection=None,
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

        assert run_call_kwargs["platforms"] == ["gemini"]


# ---------------------------------------------------------------------------
# Test: security_selections dotted keys converted to bare IDs
# ---------------------------------------------------------------------------


class TestSecuritySelectionsPassedToInstallerRun:
    """Security selections from wizard are passed as bare feature IDs."""

    def test_bare_ids_passed_through(self, monkeypatch):
        """Bare feature IDs from wizard pass through to Installer.run()."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=True)

        run_call_kwargs = {}

        def fake_render_upfront_wizard(self, ctx):
            return WizardResults(
                platforms=["claude_code"],
                security_selections={
                    "crypto": True,
                    "sleuth": False,
                },
                tts_intent=None,
                profile_selection=None,
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


# ---------------------------------------------------------------------------
# Test: tts_intent drives post-install TTS config
# ---------------------------------------------------------------------------


class TestTTSIntentDrivesPostInstallConfig:
    """tts_intent from wizard drives post-install TTS configuration."""

    def test_tts_intent_true_calls_set_tts_config_true(self, monkeypatch):
        """tts_intent=True attempts TTS setup and calls _set_tts_config(True)."""
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

    def test_tts_intent_false_calls_set_tts_config_false(self, monkeypatch):
        """tts_intent=False calls _set_tts_config(False)."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=False)

        set_tts_calls = []

        def fake_render_upfront_wizard(self, ctx):
            return WizardResults(
                platforms=["claude_code"],
                tts_intent=False,
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
            "install._set_tts_config",
            lambda enabled: set_tts_calls.append(enabled),
        )
        monkeypatch.setattr("install.show_admin_info", lambda enabled: None)
        monkeypatch.setattr("install.show_whats_new", lambda *a: None)

        from install import run_installation

        run_installation(spellbook_dir, args)

        assert set_tts_calls == [False]

    def test_tts_intent_none_does_not_call_set_tts_config(self, monkeypatch):
        """tts_intent=None (skipped) does not call _set_tts_config."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=False)

        set_tts_calls = []

        def fake_render_upfront_wizard(self, ctx):
            return WizardResults(
                platforms=["claude_code"],
                tts_intent=None,
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
            "install._set_tts_config",
            lambda enabled: set_tts_calls.append(enabled),
        )
        monkeypatch.setattr("install.show_admin_info", lambda enabled: None)
        monkeypatch.setattr("install.show_whats_new", lambda *a: None)

        from install import run_installation

        run_installation(spellbook_dir, args)

        assert set_tts_calls == []


# ---------------------------------------------------------------------------
# Test: profile_selection applied immediately
# ---------------------------------------------------------------------------


class TestProfileSelectionAppliedImmediately:
    """Profile from wizard results is applied immediately via config_set."""

    def test_profile_set_via_config_set(self, monkeypatch):
        """profile_selection='zen' calls config_set('profile.default', 'zen')."""
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
# Test: --reconfigure path preserved
# ---------------------------------------------------------------------------


class TestReconfigurePathPreserved:
    """--reconfigure still uses render_config_wizard, NOT the upfront wizard."""

    def test_reconfigure_does_not_call_upfront_wizard(self, monkeypatch):
        """--reconfigure calls render_config_wizard, not render_upfront_wizard."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(reconfigure=True, dry_run=True)

        upfront_called = []

        def fake_render_upfront_wizard(self, ctx):
            upfront_called.append(True)
            return WizardResults()

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_config_wizard",
            lambda self, unset_keys, existing_config, is_upgrade: {},
        )
        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_profile_wizard",
            lambda self, reconfigure=False: {},
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
        monkeypatch.setattr(
            "spellbook.core.config.get_unset_config_keys",
            lambda: [],
        )

        from install import run_installation

        result = run_installation(spellbook_dir, args)

        assert upfront_called == []
        assert result == 0


# ---------------------------------------------------------------------------
# Test: WizardContext assembly
# ---------------------------------------------------------------------------


class TestWizardContextAssembly:
    """Verify WizardContext is assembled with correct values from CLI args."""

    def test_context_has_correct_cli_platforms(self, monkeypatch):
        """--platforms=gemini sets WizardContext.cli_platforms=['gemini']."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(platforms="gemini", yes=True, dry_run=True)

        captured_ctx = []

        def fake_render_upfront_wizard(self, ctx):
            captured_ctx.append(ctx)
            return WizardResults(
                platforms=ctx.cli_platforms or ctx.available_platforms,
            )

        def fake_installer_run(self, **kwargs):
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

        assert len(captured_ctx) == 1
        assert captured_ctx[0].cli_platforms == ["gemini"]

    def test_context_no_tts_flag(self, monkeypatch):
        """--no-tts sets WizardContext.tts_disabled=True."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(no_tts=True, yes=True, dry_run=True)

        captured_ctx = []

        def fake_render_upfront_wizard(self, ctx):
            captured_ctx.append(ctx)
            return WizardResults(platforms=ctx.available_platforms, tts_intent=False)

        def fake_installer_run(self, **kwargs):
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

        assert len(captured_ctx) == 1
        assert captured_ctx[0].tts_disabled is True

    def test_context_security_level_flag(self, monkeypatch):
        """--security-level=standard sets WizardContext.security_level='standard'."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(security_level="standard", yes=True, dry_run=True)

        captured_ctx = []

        def fake_render_upfront_wizard(self, ctx):
            captured_ctx.append(ctx)
            return WizardResults(platforms=ctx.available_platforms)

        def fake_installer_run(self, **kwargs):
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

        assert len(captured_ctx) == 1
        assert captured_ctx[0].security_level == "standard"

    def test_context_auto_yes_flag(self, monkeypatch):
        """--yes sets WizardContext.auto_yes=True."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=True)

        captured_ctx = []

        def fake_render_upfront_wizard(self, ctx):
            captured_ctx.append(ctx)
            return WizardResults(platforms=ctx.available_platforms)

        def fake_installer_run(self, **kwargs):
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

        assert len(captured_ctx) == 1
        assert captured_ctx[0].auto_yes is True

    def test_context_no_interactive_flag(self, monkeypatch):
        """--no-interactive sets WizardContext.no_interactive=True."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(no_interactive=True, dry_run=True)

        captured_ctx = []

        def fake_render_upfront_wizard(self, ctx):
            captured_ctx.append(ctx)
            return WizardResults(platforms=ctx.available_platforms)

        def fake_installer_run(self, **kwargs):
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

        assert len(captured_ctx) == 1
        assert captured_ctx[0].no_interactive is True


# ---------------------------------------------------------------------------
# Test: --security-level bypasses wizard, uses level_to_selections
# ---------------------------------------------------------------------------


class TestSecurityLevelFlagBypassesWizard:
    """--security-level overrides wizard security_selections."""

    def test_security_level_standard_passes_to_installer(self, monkeypatch):
        """--security-level=standard converts to selections and passes to Installer.run()."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(security_level="standard", yes=True, dry_run=True)

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

        assert run_call_kwargs["security_selections"] == {
            "spotlighting": True,
            "crypto": True,
            "sleuth": False,
            "lodo": False,
        }


# ---------------------------------------------------------------------------
# Test: old post-install wizards not called in new flow
# ---------------------------------------------------------------------------


class TestPostInstallWizardsReplaced:
    """Old post-install profile and TTS wizards replaced by upfront wizard."""

    def test_render_tts_wizard_not_called_when_wizard_results_exist(self, monkeypatch):
        """render_tts_wizard is NOT called when wizard_results has tts_intent."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=False)

        tts_wizard_calls = []

        def fake_render_upfront_wizard(self, ctx):
            return WizardResults(
                platforms=["claude_code"],
                tts_intent=True,
            )

        original_render_tts_wizard = None

        def fake_render_tts_wizard(self):
            tts_wizard_calls.append(True)
            return {}

        def fake_installer_run(self, **kwargs):
            return _make_session(dry_run=False)

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_tts_wizard",
            fake_render_tts_wizard,
        )
        monkeypatch.setattr(
            "installer.core.Installer.run",
            fake_installer_run,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
        monkeypatch.setattr("install.check_tts_available", lambda: True)
        monkeypatch.setattr("install._set_tts_config", lambda enabled: None)
        monkeypatch.setattr("install.show_admin_info", lambda enabled: None)
        monkeypatch.setattr("install.show_whats_new", lambda *a: None)

        from install import run_installation

        run_installation(spellbook_dir, args)

        assert tts_wizard_calls == []

    def test_render_profile_wizard_not_called_post_install(self, monkeypatch):
        """render_profile_wizard is NOT called as a separate post-install step."""
        spellbook_dir = _spellbook_dir()
        args = _make_args(yes=True, dry_run=True)

        profile_wizard_calls = []

        def fake_render_upfront_wizard(self, ctx):
            return WizardResults(
                platforms=["claude_code"],
            )

        def fake_render_profile_wizard(self, reconfigure=False):
            profile_wizard_calls.append(True)
            return {}

        def fake_installer_run(self, **kwargs):
            return _make_session()

        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_upfront_wizard",
            fake_render_upfront_wizard,
        )
        monkeypatch.setattr(
            "installer.renderer.PlainTextRenderer.render_profile_wizard",
            fake_render_profile_wizard,
        )
        monkeypatch.setattr(
            "installer.core.Installer.run",
            fake_installer_run,
        )
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

        from install import run_installation

        run_installation(spellbook_dir, args)

        assert profile_wizard_calls == []
