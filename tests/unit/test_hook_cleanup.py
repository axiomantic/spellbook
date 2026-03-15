"""Verify old shell hooks are removed and only unified hook remains."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_DIR = PROJECT_ROOT / "hooks"


class TestOldHooksRemoved:
    """Verify individual shell hooks are gone."""

    OLD_HOOKS = [
        "bash-gate.sh", "spawn-guard.sh", "state-sanitize.sh",
        "tts-timer-start.sh", "audit-log.sh", "canary-check.sh",
        "memory-inject.sh", "notify-on-complete.sh", "tts-notify.sh",
        "memory-capture.sh", "pre-compact-save.sh", "post-compact-recover.sh",
        "bash-gate.ps1", "spawn-guard.ps1", "state-sanitize.ps1",
        "tts-timer-start.ps1", "audit-log.ps1", "canary-check.ps1",
        "memory-inject.ps1", "notify-on-complete.ps1", "tts-notify.ps1",
        "memory-capture.ps1", "pre-compact-save.ps1", "post-compact-recover.ps1",
    ]

    def test_no_old_hooks_exist(self):
        for hook in self.OLD_HOOKS:
            path = HOOKS_DIR / hook
            assert not path.exists(), f"Old hook still exists: {path}"


class TestUnifiedHookExists:
    """Verify unified hook files are present."""

    def test_spellbook_hook_py_exists(self):
        assert (HOOKS_DIR / "spellbook_hook.py").exists()

    def test_spellbook_hook_ps1_exists(self):
        assert (HOOKS_DIR / "spellbook_hook.ps1").exists()

    def test_gemini_policy_preserved(self):
        assert (HOOKS_DIR / "gemini-policy.toml").exists()

    def test_opencode_plugin_preserved(self):
        assert (HOOKS_DIR / "opencode-plugin.ts").exists()
