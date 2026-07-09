"""Tests for ``_detect_platform`` in spellbook_hook.

Regression coverage for the Bash-tool subshell case: Claude Code's
``/a2a open`` Phase D tier probe runs in a Bash-tool subshell where the
always-present markers are ``CLAUDECODE=1`` / ``CLAUDE_CODE_ENTRYPOINT``
rather than the hook-only ``CLAUDE_PROJECT_DIR`` / ``CLAUDE_ENV_FILE``.
Previously such sessions were misclassified as ``"unknown"`` (Tier 0),
disabling a2a idle push delivery.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure hooks/ is on sys.path so we can import spellbook_hook directly.
HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402

# Env vars whose presence would steer detection to a non-claude platform.
_PRECEDENCE_VARS = (
    "OPENCODE",
    "CODEX_SANDBOX",
    "CODEX_SANDBOX_NETWORK_DISABLED",
    "GEMINI_CLI",
)

# Claude Code marker vars we toggle across cases.
_CLAUDE_VARS = (
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_PROJECT_DIR",
    "CLAUDE_ENV_FILE",
)


def _clear_all(monkeypatch):
    for name in _PRECEDENCE_VARS + _CLAUDE_VARS:
        monkeypatch.delenv(name, raising=False)


def test_claudecode_env_marker_detects_claude_code(monkeypatch):
    """Bash-tool subshell case: only CLAUDECODE=1 is set."""
    _clear_all(monkeypatch)
    monkeypatch.setenv("CLAUDECODE", "1")

    assert spellbook_hook._detect_platform() == "claude-code"


def test_claude_code_entrypoint_marker_detects_claude_code(monkeypatch):
    """Only CLAUDE_CODE_ENTRYPOINT is set (non-empty string)."""
    _clear_all(monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")

    assert spellbook_hook._detect_platform() == "claude-code"
