"""Tests for the unified PowerShell (.ps1) hook wrapper.

The unified hook system has a single Python entrypoint (spellbook_hook.py) with
a PowerShell wrapper (spellbook_hook.ps1) that delegates to it on Windows.

This test module validates:
- File existence of spellbook_hook.ps1
- Correct delegation structure (calls spellbook_hook.py)
- Correct stdin/stdout handling
- Old individual .ps1 hooks no longer exist

These tests run on ALL platforms (content validation, not execution).
"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_DIR = PROJECT_ROOT / "hooks"

# Old individual PS1 hooks that should no longer exist
OLD_PS1_HOOKS = [
    "bash-gate", "spawn-guard", "state-sanitize",
    "audit-log", "canary-check", "tts-timer-start",
    "tts-notify", "notify-on-complete",
    "pre-compact-save", "post-compact-recover",
    "memory-capture", "memory-inject",
]


class TestUnifiedPs1HookExists:
    """Verify spellbook_hook.ps1 exists and has correct structure."""

    def test_ps1_file_exists(self):
        path = HOOKS_DIR / "spellbook_hook.ps1"
        assert path.is_file(), f"spellbook_hook.ps1 not found at {path}"

    def test_ps1_delegates_to_python(self):
        """spellbook_hook.ps1 must invoke spellbook_hook.py."""
        path = HOOKS_DIR / "spellbook_hook.ps1"
        content = path.read_text()
        assert "spellbook_hook.py" in content, (
            "spellbook_hook.ps1 must delegate to spellbook_hook.py"
        )

    def test_ps1_handles_stdin(self):
        """spellbook_hook.ps1 must pipe stdin to the Python script."""
        path = HOOKS_DIR / "spellbook_hook.ps1"
        content = path.read_text()
        # The PS1 wrapper reads stdin and passes it to the Python script
        assert "stdin" in content.lower() or "input" in content.lower() or "Get-Content" in content or "$input" in content, (
            "spellbook_hook.ps1 must handle stdin piping"
        )


class TestOldPs1HooksRemoved:
    """Verify old individual PS1 hooks no longer exist."""

    @pytest.mark.parametrize("hook_name", OLD_PS1_HOOKS)
    def test_old_ps1_hook_does_not_exist(self, hook_name):
        path = HOOKS_DIR / f"{hook_name}.ps1"
        assert not path.exists(), f"Old PS1 hook still exists: {path}"


class TestUnifiedPyHookExists:
    """Verify the unified Python hook exists."""

    def test_py_file_exists(self):
        path = HOOKS_DIR / "spellbook_hook.py"
        assert path.is_file(), f"spellbook_hook.py not found at {path}"

    def test_py_has_python_shebang(self):
        path = HOOKS_DIR / "spellbook_hook.py"
        with open(path) as f:
            first_line = f.readline()
        assert first_line.strip() == "#!/usr/bin/env python3"
