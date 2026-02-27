"""Tests for TTS detection and setup in install.py.

Task 16: The installer should detect whether kokoro is importable and,
if available, prompt the user to enable TTS. The --yes flag auto-enables,
dry-run skips, and declining sets tts_enabled=False.
"""

import builtins
import sys
from unittest.mock import patch, MagicMock

# install.py is the top-level script; we import from it directly
from install import check_tts_available, setup_tts


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
# setup_tts() - Interactive mode
# ---------------------------------------------------------------------------


class TestSetupTtsInteractive:
    """setup_tts() in interactive mode should prompt and set config."""

    def test_prompts_user_when_kokoro_available_and_interactive(self):
        """When kokoro is available and running interactively, prompt user."""
        with patch("install.check_tts_available", return_value=True), \
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
        with patch("install.check_tts_available", return_value=True), \
             patch("install.is_interactive", return_value=True), \
             patch("builtins.input", return_value="y"), \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_success"), \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=False)
            mock_config.assert_called_once_with(True)

    def test_enables_tts_when_user_presses_enter(self):
        """Default (empty string) should accept (enable TTS)."""
        with patch("install.check_tts_available", return_value=True), \
             patch("install.is_interactive", return_value=True), \
             patch("builtins.input", return_value=""), \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_success"), \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=False)
            mock_config.assert_called_once_with(True)

    def test_disables_tts_when_user_declines(self):
        """When user answers 'n', tts_enabled should be set to False."""
        with patch("install.check_tts_available", return_value=True), \
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
        with patch("install.check_tts_available", return_value=True), \
             patch("install.is_interactive", return_value=False), \
             patch("builtins.input") as mock_input, \
             patch("install._set_tts_config") as mock_config, \
             patch("install.print_success"), \
             patch("install.print_info"):
            setup_tts(dry_run=False, auto_yes=True)
            mock_input.assert_not_called()
            mock_config.assert_called_once_with(True)


# ---------------------------------------------------------------------------
# setup_tts() - Dry-run and kokoro-unavailable
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

    def test_kokoro_unavailable_skips_tts(self):
        """When kokoro is not available, TTS setup should be skipped."""
        with patch("install.check_tts_available", return_value=False), \
             patch("builtins.input") as mock_input, \
             patch("install._set_tts_config") as mock_config:
            setup_tts(dry_run=False, auto_yes=False)
            mock_input.assert_not_called()
            mock_config.assert_not_called()
