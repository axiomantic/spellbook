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


# ---------------------------------------------------------------------------
# The remaining four platforms
#
# pi and opencode above rewrite a JSON entry. antigravity and forgecode do the
# same; codex and goose instead regenerate a marker-delimited block, which is a
# different mechanism and needs its own evidence.
#
# That is every installer that WRITES an MCP config, which is the population the
# CHANGELOG claim is about -- not every installer. Of the nine platform modules,
# claude_code registers by shelling out to `claude mcp add` (covered by
# test_mcp_component_has_no_token_reader, since the header would have to come
# from installer/components/mcp.py), and gemini and prime_agent write no MCP
# config at all. The write-site census in test_no_auth_header_written.py pins
# that same set of six independently.
# ---------------------------------------------------------------------------


def test_stale_header_is_stripped_from_antigravity_config(tmp_path):
    from installer.platforms.antigravity import AntigravityInstaller

    config_dir = tmp_path / "antigravity"
    config_dir.mkdir()
    config_path = config_dir / "mcp_config.json"
    config_path.write_text(json.dumps({
        "mcpServers": {
            "spellbook": {
                "url": "http://127.0.0.1:8765/mcp",
                "transport": "http",
                "headers": {"Authorization": "Bearer stale-secret"},
            },
            "other": {"url": "http://example.invalid", "headers": {"X-Keep": "1"}},
        }
    }))

    installer = AntigravityInstaller(
        spellbook_dir=tmp_path / "spellbook",
        config_dir=config_dir,
        version="0.1.0",
        dry_run=False,
    )
    success, _ = installer._update_mcp_config()

    assert success is True
    written = json.loads(config_path.read_text())
    assert "headers" not in written["mcpServers"]["spellbook"]
    assert "stale-secret" not in config_path.read_text()
    assert written["mcpServers"]["other"]["headers"] == {"X-Keep": "1"}


def test_stale_header_is_stripped_from_forgecode_config(tmp_path):
    from installer.platforms.forgecode import _update_forgecode_mcp_config

    config_path = tmp_path / ".mcp.json"
    config_path.write_text(json.dumps({
        "mcpServers": {
            "spellbook": {
                "url": "http://127.0.0.1:8765/mcp",
                "headers": {"Authorization": "Bearer stale-secret"},
            },
            "other": {"url": "http://example.invalid", "headers": {"X-Keep": "1"}},
        }
    }))

    _update_forgecode_mcp_config(config_path, dry_run=False)

    written = json.loads(config_path.read_text())
    assert "headers" not in written["mcpServers"]["spellbook"]
    assert "stale-secret" not in config_path.read_text()
    assert written["mcpServers"]["other"]["headers"] == {"X-Keep": "1"}


def test_stale_header_is_stripped_from_codex_config(tmp_path):
    """codex uses marker-block regeneration, not entry replacement."""
    from installer.platforms.codex import (
        TOML_END_MARKER,
        TOML_START_MARKER,
        _add_mcp_to_config_toml,
    )

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[some_other_tool]\nkeep = true\n\n"
        f"{TOML_START_MARKER}\n"
        "[mcp_servers.spellbook]\n"
        'url = "http://127.0.0.1:8765/mcp"\n'
        'http_headers = { Authorization = "Bearer stale-secret" }\n'
        f"{TOML_END_MARKER}\n"
    )

    _add_mcp_to_config_toml(config_path, dry_run=False)

    written = config_path.read_text()
    assert "stale-secret" not in written
    assert "Authorization" not in written
    assert "[some_other_tool]" in written


def test_stale_header_is_stripped_from_goose_config(tmp_path):
    """goose uses marker-block regeneration, not entry replacement."""
    from installer.platforms.goose import (
        SPELLBOOK_END_MARKER,
        SPELLBOOK_START_MARKER,
        _update_goose_mcp_config,
    )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "extensions:\n"
        f"{SPELLBOOK_START_MARKER}\n"
        "  - type: streamable_http\n"
        "    name: spellbook\n"
        "    uri: http://127.0.0.1:8765/mcp\n"
        '    headers: {Authorization: "Bearer stale-secret"}\n'
        f"{SPELLBOOK_END_MARKER}\n"
    )

    _update_goose_mcp_config(config_path, dry_run=False)

    written = config_path.read_text()
    assert "stale-secret" not in written
    assert "Authorization" not in written
    assert "headers: {}" in written
