"""
Unit tests for Antigravity platform installer.
"""



from installer.platforms.antigravity import AntigravityInstaller


def test_antigravity_properties(tmp_path):
    installer = AntigravityInstaller(
        spellbook_dir=tmp_path / "spellbook",
        config_dir=tmp_path / "antigravity",
        version="0.1.0",
    )
    assert installer.platform_name == "Antigravity"
    assert installer.platform_id == "antigravity"
    assert installer.mcp_config_path == tmp_path / "antigravity" / "mcp_config.json"


def test_antigravity_detect_not_installed(tmp_path):
    config_dir = tmp_path / "antigravity"
    installer = AntigravityInstaller(
        spellbook_dir=tmp_path / "spellbook",
        config_dir=config_dir,
        version="0.1.0",
    )
    status = installer.detect()
    assert status.platform == "antigravity"
    assert status.available is True
    assert status.installed is False
    assert status.version is None


def test_antigravity_mcp_config_update(tmp_path):
    config_dir = tmp_path / "antigravity"
    installer = AntigravityInstaller(
        spellbook_dir=tmp_path / "spellbook",
        config_dir=config_dir,
        version="0.1.0",
        dry_run=False,
    )
    success, msg = installer._update_mcp_config()
    assert success is True
    assert "registered MCP server" in msg

    # Verify JSON structure
    mcp_file = config_dir / "mcp_config.json"
    assert mcp_file.exists()
    import json
    data = json.loads(mcp_file.read_text())
    assert "spellbook" in data["mcpServers"]
    assert data["mcpServers"]["spellbook"]["url"] == "http://127.0.0.1:8765/mcp"
