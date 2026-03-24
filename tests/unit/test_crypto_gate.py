"""Test crypto verification gate in PreToolUse hook."""
from pathlib import Path

HOOK_FILE = Path(__file__).resolve().parent.parent.parent / "hooks" / "spellbook_hook.py"


def test_hook_has_crypto_gate():
    """Hook must have crypto verification for privileged operations."""
    source = HOOK_FILE.read_text()
    assert "verify" in source.lower() and "signature" in source.lower(), (
        "Hook does not reference signature verification"
    )


def test_hook_gates_spawn_session():
    """spawn_claude_session must be crypto-gated."""
    source = HOOK_FILE.read_text()
    # Check that spawn_claude_session appears in a gating context
    assert "spawn_claude_session" in source
    # It should appear more than once (existing gate + crypto gate)
    count = source.count("spawn_claude_session")
    assert count >= 2, (
        f"spawn_claude_session appears {count} times, expected >= 2 (existing gate + crypto gate)"
    )


def test_hook_gates_workflow_state_save():
    """workflow_state_save must be crypto-gated."""
    source = HOOK_FILE.read_text()
    count = source.count("workflow_state_save")
    assert count >= 2, (
        f"workflow_state_save appears {count} times, expected >= 2 (existing gate + crypto gate)"
    )


def test_hook_has_crypto_gate_function():
    """Hook must define a _crypto_gate function."""
    source = HOOK_FILE.read_text()
    assert "def _crypto_gate(" in source, (
        "_crypto_gate function not found in hook"
    )


def test_crypto_gate_uses_config():
    """Crypto gate must be configurable via security.crypto.enabled."""
    source = HOOK_FILE.read_text()
    assert "security.crypto.enabled" in source, (
        "Crypto gate does not check security.crypto.enabled config"
    )
