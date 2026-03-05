"""Tests for TTS hook PowerShell (.ps1) files.

Tests the .ps1 hook scripts exist and have correct structure.
On Windows, these scripts are invoked via PowerShell.
On Unix, the .sh variants run natively.
"""

import os
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_DIR = PROJECT_ROOT / "hooks"

TTS_PS1_HOOKS = {
    "tts-timer-start": HOOKS_DIR / "tts-timer-start.ps1",
    "tts-notify": HOOKS_DIR / "tts-notify.ps1",
}


# #############################################################################
# SECTION 1: PS1 file validation (runs on ALL platforms)
# #############################################################################


class TestTtsPs1HookFiles:
    """Verify that every TTS .ps1 hook file exists and has correct structure."""

    @pytest.mark.parametrize("hook_name", list(TTS_PS1_HOOKS.keys()))
    def test_hook_file_exists(self, hook_name):
        path = TTS_PS1_HOOKS[hook_name]
        assert path.is_file(), f"{hook_name}.ps1 not found at {path}"

    @pytest.mark.parametrize("hook_name", list(TTS_PS1_HOOKS.keys()))
    def test_hook_not_empty(self, hook_name):
        path = TTS_PS1_HOOKS[hook_name]
        content = path.read_text()
        assert len(content) > 50, f"{hook_name}.ps1 is suspiciously short"

    @pytest.mark.parametrize("hook_name", list(TTS_PS1_HOOKS.keys()))
    def test_hook_has_error_preference(self, hook_name):
        path = TTS_PS1_HOOKS[hook_name]
        content = path.read_text()
        assert '$ErrorActionPreference' in content

    @pytest.mark.parametrize("hook_name", list(TTS_PS1_HOOKS.keys()))
    def test_sh_counterpart_exists(self, hook_name):
        """Every .ps1 TTS hook should have a .sh counterpart."""
        sh_path = HOOKS_DIR / f"{hook_name}.sh"
        assert sh_path.is_file(), f"{hook_name}.sh not found at {sh_path}"
