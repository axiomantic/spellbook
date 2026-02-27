"""Tests for TTS detection and setup in install.py.

Task 16: The installer should detect whether kokoro is importable and,
if available, prompt the user to enable TTS. The --yes flag auto-enables,
dry-run skips, and declining sets tts_enabled=False.

When kokoro is NOT installed, the installer should offer to install it
rather than silently skipping.
"""

import builtins
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# install.py is the top-level script; we import from it directly
from install import check_tts_available, setup_tts, _set_tts_config


# All setup_tts tests need to mock config_get to avoid reading actual config.
# This context manager provides the common mock setup.
def _mock_no_prior_config():
    """Mock config_get to return None (no prior TTS preference)."""
    return patch("spellbook_mcp.config_tools.config_get", return_value=None)


# ---------------------------------------------------------------------------
# check_tts_available()
# ---------------------------------------------------------------------------


class TestCheckTtsAvailable:
    """check_tts_available() returns True iff kokoro is importable."""

    def test_returns_true_when_kokoro_importable(self):
        """When kokoro can be imported, return True."""
        kokoro_mock = MagicMock()
        with patch.dict(sys.modules, {"kokoro": kokoro_mock}):
            assert check_tts_available() is True

    def test_returns_false_when_kokoro_not_importable(self):
        """When kokoro import raises ImportError, return False."""
        _real_import = builtins.__import__

        def _fail_kokoro(name, *args, **kwargs):
            if name == "kokoro":
                raise ImportError("No module named 'kokoro'")
            return _real_import(name, *args, **kwargs)

        with patch.dict(sys.modules, {k: v for k, v in sys.modules.items() if k != "kokoro"}):
            with patch("builtins.__import__", side_effect=_fail_kokoro):
                assert check_tts_available() is False


# ---------------------------------------------------------------------------
# setup_tts() - Interactive mode (kokoro available)
# ---------------------------------------------------------------------------


class TestSetupTtsInteractive:
    """setup_tts() in interactive mode should prompt and set config."""

    def test_prompts_user_when_kokoro_available_and_interactive(self):
        """When kokoro is available and running interactively, prompt user."""
        with _mock_no_prior_config(), \
             patch("install.check_tts_available", return_value=True), \
             patch("install.is_interactive", return_value=True), \
             patch("builtins.input", return_value="y") as mock_input, \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_success"), \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=False)
            mock_input.assert_called_once()
            assert "TTS" in mock_input.call_args[0][0] or "tts" in mock_input.call_args[0][0].lower()

    def test_enables_tts_when_user_accepts(self):
        """When user answers 'y', tts_enabled should be set to True."""
        with _mock_no_prior_config(), \
             patch("install.check_tts_available", return_value=True), \
             patch("install.is_interactive", return_value=True), \
             patch("builtins.input", return_value="y"), \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_success"), \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=False)
            mock_config.assert_called_once_with(True)

    def test_enables_tts_when_user_presses_enter(self):
        """Default (empty string) should accept (enable TTS)."""
        with _mock_no_prior_config(), \
             patch("install.check_tts_available", return_value=True), \
             patch("install.is_interactive", return_value=True), \
             patch("builtins.input", return_value=""), \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_success"), \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=False)
            mock_config.assert_called_once_with(True)

    def test_disables_tts_when_user_declines(self):
        """When user answers 'n', tts_enabled should be set to False."""
        with _mock_no_prior_config(), \
             patch("install.check_tts_available", return_value=True), \
             patch("install.is_interactive", return_value=True), \
             patch("builtins.input", return_value="n"), \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_success"), \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=False)
            mock_config.assert_called_once_with(False)


# ---------------------------------------------------------------------------
# setup_tts() - Auto-yes mode
# ---------------------------------------------------------------------------


class TestSetupTtsAutoYes:
    """setup_tts() with auto_yes=True should enable without prompting."""

    def test_auto_yes_enables_tts_without_prompt(self):
        """--yes flag should auto-enable TTS without user input."""
        with _mock_no_prior_config(), \
             patch("install.check_tts_available", return_value=True), \
             patch("install.is_interactive", return_value=False), \
             patch("builtins.input") as mock_input, \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_success"), \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=True)
            mock_input.assert_not_called()
            mock_config.assert_called_once_with(True)

    def test_interactive_auto_yes_enables_without_prompt(self):
        """When is_interactive()=True but auto_yes=True, no prompt shown, TTS enabled."""
        with _mock_no_prior_config(), \
             patch("install.check_tts_available", return_value=True), \
             patch("install.is_interactive", return_value=True), \
             patch("builtins.input") as mock_input, \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_success"), \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=True)
            mock_input.assert_not_called()
            mock_config.assert_called_once_with(True)


# ---------------------------------------------------------------------------
# setup_tts() - EOFError and edge cases
# ---------------------------------------------------------------------------


class TestSetupTtsEdgeCases:
    """setup_tts() handles EOFError and prompt_yn integration."""

    def test_eof_error_does_not_crash(self):
        """EOFError during input should not crash setup_tts."""
        with _mock_no_prior_config(), \
             patch("install.check_tts_available", return_value=True), \
             patch("install.is_interactive", return_value=True), \
             patch("builtins.input", side_effect=EOFError), \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_success"), \
             patch("install.print_info"):
            # Should not raise - prompt_yn handles EOFError and returns False
            setup_tts(dry_run=False, auto_yes=False)
            # When EOFError occurs, prompt_yn returns False, so TTS is disabled
            mock_config.assert_called_once_with(False)

    def test_calls_prompt_yn_with_correct_arguments(self):
        """setup_tts should call prompt_yn with default=True and auto_yes forwarded."""
        with _mock_no_prior_config(), \
             patch("install.check_tts_available", return_value=True), \
             patch("install.prompt_yn", return_value=True) as mock_prompt, \
             patch("install._set_tts_config"), \
             patch("install.print_success"), \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=False)
            mock_prompt.assert_called_once()
            _, kwargs = mock_prompt.call_args
            assert kwargs.get("default") is True
            assert kwargs.get("auto_yes") is False

    def test_calls_prompt_yn_with_auto_yes_forwarded(self):
        """setup_tts should forward auto_yes=True to prompt_yn."""
        with _mock_no_prior_config(), \
             patch("install.check_tts_available", return_value=True), \
             patch("install.prompt_yn", return_value=True) as mock_prompt, \
             patch("install._set_tts_config"), \
             patch("install.print_success"), \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=True)
            mock_prompt.assert_called_once()
            _, kwargs = mock_prompt.call_args
            assert kwargs.get("auto_yes") is True


# ---------------------------------------------------------------------------
# setup_tts() - Dry-run and skip cases
# ---------------------------------------------------------------------------


class TestSetupTtsSkipCases:
    """setup_tts() should skip TTS setup in certain conditions."""

    def test_dry_run_skips_tts(self):
        """In dry_run mode, TTS setup should be skipped entirely."""
        with patch("install.check_tts_available") as mock_check, \
             patch("install._set_tts_config") as mock_config:
            setup_tts(dry_run=True, auto_yes=False)
            mock_check.assert_not_called()
            mock_config.assert_not_called()

    def test_existing_config_skips_prompt(self):
        """When tts_enabled is already set in config, skip prompting."""
        with patch("spellbook_mcp.config_tools.config_get", return_value=True), \
             patch("install.check_tts_available", return_value=True), \
             patch("builtins.input") as mock_input, \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=False)
            mock_input.assert_not_called()
            mock_config.assert_not_called()

    def test_existing_disabled_config_skips_prompt(self):
        """When tts_enabled=False in config, skip prompting."""
        with patch("spellbook_mcp.config_tools.config_get", return_value=False), \
             patch("install.check_tts_available") as mock_check, \
             patch("builtins.input") as mock_input, \
             patch("install._set_tts_config") as mock_config:
            setup_tts(dry_run=False, auto_yes=False)
            mock_input.assert_not_called()
            mock_config.assert_not_called()


# ---------------------------------------------------------------------------
# setup_tts() - Kokoro not installed (offer to install)
# ---------------------------------------------------------------------------


class TestSetupTtsInstallOffer:
    """When kokoro is not installed, setup_tts should offer to install it."""

    def test_kokoro_unavailable_offers_install_interactive(self):
        """When kokoro not available interactively, prompt to install."""
        with _mock_no_prior_config(), \
             patch("install.check_tts_available", return_value=False), \
             patch("install.is_interactive", return_value=True), \
             patch("builtins.input", return_value="n") as mock_input, \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=False)
            # Should have prompted user
            mock_input.assert_called_once()
            # User declined, so config set to False
            mock_config.assert_called_once_with(False)

    def test_kokoro_unavailable_non_interactive_sets_disabled(self):
        """In non-interactive mode, kokoro unavailable sets tts_enabled=False."""
        with _mock_no_prior_config(), \
             patch("install.check_tts_available", return_value=False), \
             patch("install.is_interactive", return_value=False), \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=False)
            # Default for install prompt is False, so non-interactive declines
            mock_config.assert_called_once_with(False)

    def test_kokoro_unavailable_auto_yes_does_not_auto_install(self):
        """--yes should NOT auto-install heavy TTS deps."""
        with _mock_no_prior_config(), \
             patch("install.check_tts_available", return_value=False), \
             patch("install.is_interactive", return_value=False), \
             patch("install._install_tts_deps") as mock_install, \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=True)
            # auto_yes=True is passed but _install_tts_deps uses auto_yes=False
            # so in non-interactive mode, the default (False) is used
            mock_install.assert_not_called()
            mock_config.assert_called_once_with(False)

    def test_kokoro_install_success_enables_tts(self):
        """When user accepts install and it succeeds, enable TTS."""
        with _mock_no_prior_config(), \
             patch("install.check_tts_available", side_effect=[False, True]), \
             patch("install.is_interactive", return_value=True), \
             patch("builtins.input", return_value="y"), \
             patch("install._install_tts_deps", return_value=True) as mock_install, \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_success"), \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=False, spellbook_dir=Path("/fake"))
            mock_install.assert_called_once_with(Path("/fake"))
            mock_config.assert_called_once_with(True)

    def test_kokoro_install_failure_shows_error(self):
        """When install fails, show error message."""
        with _mock_no_prior_config(), \
             patch("install.check_tts_available", return_value=False), \
             patch("install.is_interactive", return_value=True), \
             patch("builtins.input", return_value="y"), \
             patch("install._install_tts_deps", return_value=False), \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_error") as mock_error, \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=False, spellbook_dir=Path("/fake"))
            mock_error.assert_called_once()
            mock_config.assert_not_called()


# ---------------------------------------------------------------------------
# _set_tts_config() direct test
# ---------------------------------------------------------------------------


class TestSetTtsConfig:
    """_set_tts_config() persists the tts_enabled config value."""

    def test_writes_tts_enabled_to_config(self, tmp_path):
        """Calling _set_tts_config writes tts_enabled to the config file."""
        config_file = tmp_path / "spellbook.json"
        config_file.write_text("{}")
        with patch("spellbook_mcp.config_tools.get_config_path", return_value=config_file), \
             patch("spellbook_mcp.config_tools.CONFIG_LOCK_PATH", tmp_path / "config.lock"):
            _set_tts_config(True)
        data = json.loads(config_file.read_text())
        assert data["tts_enabled"] is True

    def test_writes_tts_disabled_to_config(self, tmp_path):
        """Calling _set_tts_config(False) writes tts_enabled=False."""
        config_file = tmp_path / "spellbook.json"
        config_file.write_text("{}")
        with patch("spellbook_mcp.config_tools.get_config_path", return_value=config_file), \
             patch("spellbook_mcp.config_tools.CONFIG_LOCK_PATH", tmp_path / "config.lock"):
            _set_tts_config(False)
        data = json.loads(config_file.read_text())
        assert data["tts_enabled"] is False
