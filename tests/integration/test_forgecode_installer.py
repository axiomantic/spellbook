"""Tests for ForgeCode platform installer.

ForgeCode (tailcallhq/forgecode) uses HTTP transport to connect to the
spellbook MCP daemon, with a Claude Code style top-level ``mcpServers``
entry written to ``<config_dir>/.mcp.json`` (mode 0600), plus an AGENTS.md
demarcated section.

Reference: design doc Section 3 (class skeleton) and Section 7 (test cases).
"""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from installer.components.mcp import DEFAULT_HOST, DEFAULT_PORT
from installer.demarcation import MARKER_END, MARKER_START_PATTERN

DAEMON_URL = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/mcp"
TEST_TOKEN = "test-token-xyz"
TEST_VERSION = "0.1.0"


def _make_spellbook_dir(tmp_path: Path) -> Path:
    """Create a minimal mock spellbook source directory."""
    spellbook = tmp_path / "spellbook_src"
    spellbook.mkdir()
    (spellbook / ".version").write_text(TEST_VERSION)
    (spellbook / "AGENTS.spellbook.md").write_text("# Spellbook Context\n\nTest content.\n")
    return spellbook


@pytest.fixture
def spellbook_dir(tmp_path):
    return _make_spellbook_dir(tmp_path)


@pytest.fixture
def forge_config_dir(tmp_path):
    """Create the default ~/.forge config dir under tmp_path."""
    cfg = tmp_path / ".forge"
    cfg.mkdir()
    return cfg


@pytest.fixture
def patched_home_and_token(tmp_path, monkeypatch):
    """Pin ``Path.home()`` to tmp_path and stub ``get_mcp_auth_token``.

    All forge-relevant ``Path.home()`` lookups (legacy ``~/forge``, default
    ``~/.forge``) resolve under tmp_path, isolating the test from the real
    user environment. The auth token is stubbed at the import site so the
    installer always sees TEST_TOKEN regardless of the real token file.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Patch the imported reference in the forgecode module (where it is used).
    import installer.platforms.forgecode as fc_mod

    monkeypatch.setattr(fc_mod, "get_mcp_auth_token", lambda: TEST_TOKEN)
    monkeypatch.delenv("FORGE_CONFIG", raising=False)
    return tmp_path


def _make_installer(spellbook_dir, forge_config_dir, dry_run=False):
    from installer.platforms.forgecode import ForgeCodeInstaller

    return ForgeCodeInstaller(
        spellbook_dir, forge_config_dir, TEST_VERSION, dry_run=dry_run
    )


def _expected_spellbook_entry():
    return {
        "url": DAEMON_URL,
        "oauth": False,
        "headers": {"Authorization": f"Bearer {TEST_TOKEN}"},
    }


class TestForgeCodeInstall:
    """Phase B install behavior tests."""

    def test_fresh_install_creates_mcp_json_with_correct_structure(
        self, spellbook_dir, forge_config_dir, patched_home_and_token
    ):
        installer = _make_installer(spellbook_dir, forge_config_dir)
        installer.install()

        mcp_path = forge_config_dir / ".mcp.json"
        actual = json.loads(mcp_path.read_text(encoding="utf-8"))

        assert actual == {"mcpServers": {"spellbook": _expected_spellbook_entry()}}

    def test_fresh_install_writes_AGENTS_md_with_demarcated_section(
        self, spellbook_dir, forge_config_dir, patched_home_and_token
    ):
        installer = _make_installer(spellbook_dir, forge_config_dir)
        installer.install()

        agents_md = forge_config_dir / "AGENTS.md"
        content = agents_md.read_text(encoding="utf-8")

        from installer.components.context_files import generate_codex_context

        expected_spellbook_content = generate_codex_context(spellbook_dir)
        expected_start = f"<!-- SPELLBOOK:START version={TEST_VERSION} -->"
        expected = (
            expected_start
            + "\n"
            + expected_spellbook_content
            + "\n"
            + MARKER_END
            + "\n"
        )
        assert content == expected

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes only")
    def test_fresh_install_chmod_0600(
        self, spellbook_dir, forge_config_dir, patched_home_and_token
    ):
        installer = _make_installer(spellbook_dir, forge_config_dir)
        installer.install()

        mcp_path = forge_config_dir / ".mcp.json"
        actual_mode = stat.S_IMODE(os.stat(mcp_path).st_mode)
        assert actual_mode == 0o600

    def test_install_sets_oauth_false(
        self, spellbook_dir, forge_config_dir, patched_home_and_token
    ):
        installer = _make_installer(spellbook_dir, forge_config_dir)
        installer.install()

        actual = json.loads((forge_config_dir / ".mcp.json").read_text(encoding="utf-8"))
        assert actual["mcpServers"]["spellbook"]["oauth"] is False

    def test_install_writes_authorization_bearer_header(
        self, spellbook_dir, forge_config_dir, patched_home_and_token
    ):
        installer = _make_installer(spellbook_dir, forge_config_dir)
        installer.install()

        actual = json.loads((forge_config_dir / ".mcp.json").read_text(encoding="utf-8"))
        assert actual["mcpServers"]["spellbook"]["headers"] == {
            "Authorization": f"Bearer {TEST_TOKEN}"
        }

    def test_install_top_level_key_is_mcpServers(
        self, spellbook_dir, forge_config_dir, patched_home_and_token
    ):
        installer = _make_installer(spellbook_dir, forge_config_dir)
        installer.install()

        actual = json.loads((forge_config_dir / ".mcp.json").read_text(encoding="utf-8"))
        # Claude-Code style: top-level key is "mcpServers", NOT "mcp" (OpenCode shape).
        assert list(actual.keys()) == ["mcpServers"]

    def test_install_with_FORGE_CONFIG_set(
        self, spellbook_dir, tmp_path, monkeypatch
    ):
        custom = tmp_path / "custom-forge"
        custom.mkdir()

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        import installer.platforms.forgecode as fc_mod

        monkeypatch.setattr(fc_mod, "get_mcp_auth_token", lambda: TEST_TOKEN)
        monkeypatch.setenv("FORGE_CONFIG", str(custom))

        # config_dir passed to installer is the custom one (resolve_config_dirs
        # honored the env var; installer should not second-guess it).
        installer = _make_installer(spellbook_dir, custom)
        installer.install()

        actual = json.loads((custom / ".mcp.json").read_text(encoding="utf-8"))
        assert actual == {"mcpServers": {"spellbook": _expected_spellbook_entry()}}
        # Default ~/.forge should not have been created or written.
        assert not (tmp_path / ".forge").exists()

    def test_install_prefers_legacy_forge_dir_when_pre_existing(
        self, spellbook_dir, tmp_path, monkeypatch
    ):
        # Pre-existing legacy ~/forge.
        legacy = tmp_path / "forge"
        legacy.mkdir()
        # Default ~/.forge also exists (the configured default).
        default = tmp_path / ".forge"
        default.mkdir()

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        import installer.platforms.forgecode as fc_mod

        monkeypatch.setattr(fc_mod, "get_mcp_auth_token", lambda: TEST_TOKEN)
        monkeypatch.delenv("FORGE_CONFIG", raising=False)

        installer = _make_installer(spellbook_dir, default)
        installer.install()

        legacy_actual = json.loads((legacy / ".mcp.json").read_text(encoding="utf-8"))
        assert legacy_actual == {"mcpServers": {"spellbook": _expected_spellbook_entry()}}
        # Default dir is left untouched.
        assert not (default / ".mcp.json").exists()
        assert not (default / "AGENTS.md").exists()

    def test_install_merges_existing_mcp_json_preserving_other_servers(
        self, spellbook_dir, forge_config_dir, patched_home_and_token
    ):
        existing = {
            "mcpServers": {
                "foo": {"url": "http://other:9999/mcp", "oauth": True},
            }
        }
        mcp_path = forge_config_dir / ".mcp.json"
        mcp_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

        installer = _make_installer(spellbook_dir, forge_config_dir)
        installer.install()

        actual = json.loads(mcp_path.read_text(encoding="utf-8"))
        assert actual == {
            "mcpServers": {
                "foo": {"url": "http://other:9999/mcp", "oauth": True},
                "spellbook": _expected_spellbook_entry(),
            }
        }

    def test_install_demarcation_preserves_existing_AGENTS_md(
        self, spellbook_dir, forge_config_dir, patched_home_and_token
    ):
        agents_md = forge_config_dir / "AGENTS.md"
        user_content = "# user content\n\nMy own rules here.\n"
        agents_md.write_text(user_content, encoding="utf-8")

        installer = _make_installer(spellbook_dir, forge_config_dir)
        installer.install()

        new_content = agents_md.read_text(encoding="utf-8")

        # User content must come first, byte-for-byte preserved.
        assert new_content.startswith(user_content)

        # Demarcated section must follow with the correct version marker and END marker.
        from installer.components.context_files import generate_codex_context

        expected_spellbook = generate_codex_context(spellbook_dir)
        expected_start = f"<!-- SPELLBOOK:START version={TEST_VERSION} -->"
        # Build the expected complete file using the same logic the implementation uses.
        expected = (
            user_content
            + "\n"
            + expected_start
            + "\n"
            + expected_spellbook
            + "\n"
            + MARKER_END
            + "\n"
        )
        assert new_content == expected

    def test_install_warns_when_FORGE_CONFIG_unset(
        self, spellbook_dir, forge_config_dir, patched_home_and_token
    ):
        # Real install (NOT dry_run) so the env_warning gating runs.
        installer = _make_installer(spellbook_dir, forge_config_dir, dry_run=False)
        results = installer.install()

        warnings = [r for r in results if r.component == "env_warning"]
        assert len(warnings) == 1
        warning = warnings[0]
        assert warning.platform == "forgecode"
        assert warning.success is True
        assert warning.action == "warned"
        # Full message construction (must match installer copy exactly).
        assert warning.message == (
            "FORGE_CONFIG not set at install time; future forge sessions "
            "that set FORGE_CONFIG to a different path will not see this install"
        )

    @pytest.mark.skip(
        reason="Round-trip MVP test deferred: no daemon harness in tests/. "
        "Follow-up to design Section 12 #5."
    )
    def test_round_trip_session_init(self):
        """Mocked forge session POSTs spellbook_session_init to the daemon.

        Deferred: ``tests/integration/test_opencode_installer.py`` does not
        define a ``daemon_for_test`` fixture, so there is no daemon test
        harness to reuse. Implementing one is out of scope for Phase B.
        """

    def test_uninstall_removes_only_spellbook_entry(
        self, spellbook_dir, forge_config_dir, patched_home_and_token
    ):
        existing = {
            "mcpServers": {
                "foo": {"url": "http://other:9999/mcp", "oauth": True},
                "spellbook": {
                    "url": DAEMON_URL,
                    "oauth": False,
                    "headers": {"Authorization": f"Bearer {TEST_TOKEN}"},
                },
            }
        }
        mcp_path = forge_config_dir / ".mcp.json"
        mcp_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

        installer = _make_installer(spellbook_dir, forge_config_dir)
        installer.uninstall()

        actual = json.loads(mcp_path.read_text(encoding="utf-8"))
        assert actual == {
            "mcpServers": {
                "foo": {"url": "http://other:9999/mcp", "oauth": True},
            }
        }

    def test_mcp_server_name_collision_overwrites(
        self, spellbook_dir, forge_config_dir, patched_home_and_token
    ):
        # Pre-existing stale spellbook entry should be replaced wholesale.
        existing = {
            "mcpServers": {
                "spellbook": {
                    "url": "http://stale-host:1234/mcp",
                    "oauth": True,
                    "headers": {"Authorization": "Bearer old-token"},
                }
            }
        }
        mcp_path = forge_config_dir / ".mcp.json"
        mcp_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

        installer = _make_installer(spellbook_dir, forge_config_dir)
        installer.install()

        actual = json.loads(mcp_path.read_text(encoding="utf-8"))
        assert actual == {"mcpServers": {"spellbook": _expected_spellbook_entry()}}

    def test_install_with_invalid_FORGE_CONFIG_path_skips(
        self, spellbook_dir, tmp_path, monkeypatch
    ):
        bogus = tmp_path / "nonexistent" / "path" / "that" / "does" / "not" / "exist"
        # Note: do NOT mkdir; must remain absent.
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        import installer.platforms.forgecode as fc_mod

        monkeypatch.setattr(fc_mod, "get_mcp_auth_token", lambda: TEST_TOKEN)
        monkeypatch.setenv("FORGE_CONFIG", str(bogus))

        installer = _make_installer(spellbook_dir, bogus)
        results = installer.install()

        assert len(results) == 1
        result = results[0]
        assert result.component == "platform"
        assert result.platform == "forgecode"
        assert result.success is True
        assert result.action == "skipped"
        assert result.message == f"{bogus} not found"
        # No file written.
        assert not bogus.exists()


class TestForgeCodeInCore:
    """Verify ForgeCodeInstaller is registered in the core dispatcher."""

    def test_get_platform_installer_returns_forgecode(
        self, spellbook_dir, tmp_path, monkeypatch
    ):
        from installer.core import get_platform_installer
        from installer.platforms.forgecode import ForgeCodeInstaller

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        installer = get_platform_installer(
            "forgecode", spellbook_dir, TEST_VERSION, dry_run=True
        )
        assert isinstance(installer, ForgeCodeInstaller)
