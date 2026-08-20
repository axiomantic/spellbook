"""Migration: existing installs must not be left holding an inert credential.

Two artifacts survive an upgrade from bearer-token auth: the token file, and an
Authorization header already written into a platform config. A header the daemon
ignores is harmless but indistinguishable from one that works, so both are
removed rather than left inert.
"""

import json

from installer.migrations import remove_legacy_mcp_token


def test_removes_existing_token_file(tmp_path):
    token = tmp_path / ".mcp-token"
    token.write_text("stale-secret")

    assert remove_legacy_mcp_token(token) is True
    assert not token.exists()


def test_is_idempotent_when_no_token_file(tmp_path):
    """Safe on a machine that never had a token."""
    assert remove_legacy_mcp_token(tmp_path / "absent") is False


def test_reports_false_when_path_is_a_directory(tmp_path):
    """An unlink failure is reported, not raised."""
    stuck = tmp_path / "adir"
    stuck.mkdir()
    assert remove_legacy_mcp_token(stuck) is False


def test_stale_header_is_stripped_from_pi_config(tmp_path):
    """Re-running install drops an Authorization header from a prior version."""
    from installer.platforms.pi import _update_pi_mcp_config

    config_path = tmp_path / "mcp.json"
    config_path.write_text(json.dumps({
        "mcpServers": {
            "spellbook": {
                "url": "http://127.0.0.1:8765/mcp",
                "headers": {"Authorization": "Bearer stale-secret"},
            },
            "other": {"url": "http://example.invalid", "headers": {"X-Keep": "1"}},
        }
    }))

    _update_pi_mcp_config(config_path, dry_run=False)

    written = json.loads(config_path.read_text())
    assert "headers" not in written["mcpServers"]["spellbook"]
    assert "stale-secret" not in config_path.read_text()
    # An unrelated server's headers are the user's, not ours to touch.
    assert written["mcpServers"]["other"]["headers"] == {"X-Keep": "1"}


def test_stale_header_is_stripped_from_opencode_config(tmp_path):
    from installer.platforms.opencode import _update_opencode_config

    config_path = tmp_path / "opencode.json"
    config_path.write_text(json.dumps({
        "mcp": {
            "spellbook": {
                "type": "remote",
                "url": "http://127.0.0.1:8765/mcp",
                "enabled": True,
                "headers": {"Authorization": "Bearer stale-secret"},
            }
        }
    }))

    _update_opencode_config(config_path, dry_run=False)

    written = json.loads(config_path.read_text())
    assert "headers" not in written["mcp"]["spellbook"]
    assert "stale-secret" not in config_path.read_text()
