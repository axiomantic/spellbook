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

import tripwire
import pytest

import installer.platforms.forgecode as fc_mod
from installer.components.context_files import generate_codex_context
from installer.components.mcp import DEFAULT_HOST, DEFAULT_PORT
from installer.demarcation import MARKER_END
from installer.platforms.forgecode import ForgeCodeInstaller

DAEMON_URL = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/mcp"
TEST_TOKEN = "test-token-xyz"
TEST_VERSION = "0.1.0"

# Module path used in tripwire mock targets.
FC_MOD = "installer.platforms.forgecode"


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
def forge_env(monkeypatch, forge_config_dir):
    """Pin FORGE_CONFIG to the test config dir (allowed via monkeypatch.setenv).

    Setting FORGE_CONFIG short-circuits ``_resolve_effective_config_dir`` so
    no ``Path.home()`` lookups are needed for the common-case install tests.
    Tests that intentionally exercise ``Path.home()`` resolution (legacy
    ``~/forge`` preference, FORGE_CONFIG-unset warning) override this with
    their own tripwire mock.
    """
    monkeypatch.setenv("FORGE_CONFIG", str(forge_config_dir))
    return forge_config_dir


def _make_installer(spellbook_dir, forge_config_dir, dry_run=False):
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
        self, spellbook_dir, forge_config_dir, forge_env
    ):
        m_token = tripwire.mock(f"{FC_MOD}:get_mcp_auth_token").returns(TEST_TOKEN)
        installer = _make_installer(spellbook_dir, forge_config_dir)
        with tripwire:
            installer.install()
        m_token.assert_call()

        mcp_path = forge_config_dir / ".mcp.json"
        actual = json.loads(mcp_path.read_text(encoding="utf-8"))

        assert actual == {"mcpServers": {"spellbook": _expected_spellbook_entry()}}

    def test_fresh_install_writes_AGENTS_md_with_demarcated_section(
        self, spellbook_dir, forge_config_dir, forge_env
    ):
        m_token = tripwire.mock(f"{FC_MOD}:get_mcp_auth_token").returns(TEST_TOKEN)
        installer = _make_installer(spellbook_dir, forge_config_dir)
        with tripwire:
            installer.install()
        m_token.assert_call()

        agents_md = forge_config_dir / "AGENTS.md"
        content = agents_md.read_text(encoding="utf-8")

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
        self, spellbook_dir, forge_config_dir, forge_env
    ):
        m_token = tripwire.mock(f"{FC_MOD}:get_mcp_auth_token").returns(TEST_TOKEN)
        installer = _make_installer(spellbook_dir, forge_config_dir)
        with tripwire:
            installer.install()
        m_token.assert_call()

        mcp_path = forge_config_dir / ".mcp.json"
        actual_mode = stat.S_IMODE(os.stat(mcp_path).st_mode)
        assert actual_mode == 0o600

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="POSIX file modes; Windows chmod is a no-op",
    )
    def test_install_tightens_existing_mcp_json_permissions(
        self, spellbook_dir, forge_config_dir, forge_env
    ):
        """An existing .mcp.json with broad mode (0o644) must be tightened to 0o600.

        Regression for cycle-4 review: ``os.open(..., 0o600)`` only applies
        the mode on creation, so without an explicit ``os.fchmod`` an
        existing file's permissions survive ``O_TRUNC`` and the bearer
        token leaks to other local users.
        """
        mcp_path = forge_config_dir / ".mcp.json"
        # Pre-create with broad perms (0o644) and minimal valid content.
        mcp_path.write_text("{}\n", encoding="utf-8")
        os.chmod(mcp_path, 0o644)
        assert stat.S_IMODE(os.stat(mcp_path).st_mode) == 0o644

        m_token = tripwire.mock(f"{FC_MOD}:get_mcp_auth_token").returns(TEST_TOKEN)
        installer = _make_installer(spellbook_dir, forge_config_dir)
        with tripwire:
            installer.install()
        m_token.assert_call()

        actual_mode = stat.S_IMODE(os.stat(mcp_path).st_mode)
        assert actual_mode == 0o600, (
            f"expected pre-existing 0o644 .mcp.json to be tightened to 0o600, "
            f"got {oct(actual_mode)}"
        )

    def test_install_sets_oauth_false(
        self, spellbook_dir, forge_config_dir, forge_env
    ):
        m_token = tripwire.mock(f"{FC_MOD}:get_mcp_auth_token").returns(TEST_TOKEN)
        installer = _make_installer(spellbook_dir, forge_config_dir)
        with tripwire:
            installer.install()
        m_token.assert_call()

        actual = json.loads((forge_config_dir / ".mcp.json").read_text(encoding="utf-8"))
        assert actual["mcpServers"]["spellbook"]["oauth"] is False

    def test_install_writes_authorization_bearer_header(
        self, spellbook_dir, forge_config_dir, forge_env
    ):
        m_token = tripwire.mock(f"{FC_MOD}:get_mcp_auth_token").returns(TEST_TOKEN)
        installer = _make_installer(spellbook_dir, forge_config_dir)
        with tripwire:
            installer.install()
        m_token.assert_call()

        actual = json.loads((forge_config_dir / ".mcp.json").read_text(encoding="utf-8"))
        assert actual["mcpServers"]["spellbook"]["headers"] == {
            "Authorization": f"Bearer {TEST_TOKEN}"
        }

    def test_install_top_level_key_is_mcpServers(
        self, spellbook_dir, forge_config_dir, forge_env
    ):
        m_token = tripwire.mock(f"{FC_MOD}:get_mcp_auth_token").returns(TEST_TOKEN)
        installer = _make_installer(spellbook_dir, forge_config_dir)
        with tripwire:
            installer.install()
        m_token.assert_call()

        actual = json.loads((forge_config_dir / ".mcp.json").read_text(encoding="utf-8"))
        # Claude-Code style: top-level key is "mcpServers", NOT "mcp" (OpenCode shape).
        assert list(actual.keys()) == ["mcpServers"]

    def test_install_with_FORGE_CONFIG_set(
        self, spellbook_dir, tmp_path, monkeypatch
    ):
        custom = tmp_path / "custom-forge"
        custom.mkdir()

        # FORGE_CONFIG is allowed via monkeypatch.setenv per styleguide.
        monkeypatch.setenv("FORGE_CONFIG", str(custom))

        m_token = tripwire.mock(f"{FC_MOD}:get_mcp_auth_token").returns(TEST_TOKEN)
        # config_dir passed to installer is the custom one (resolve_config_dirs
        # honored the env var; installer should not second-guess it).
        installer = _make_installer(spellbook_dir, custom)
        with tripwire:
            installer.install()
        m_token.assert_call()

        actual = json.loads((custom / ".mcp.json").read_text(encoding="utf-8"))
        assert actual == {"mcpServers": {"spellbook": _expected_spellbook_entry()}}
        # Default ~/.forge should not have been created or written.
        assert not (tmp_path / ".forge").exists()

    def test_install_prefers_legacy_forge_dir_when_pre_existing(
        self, spellbook_dir, tmp_path, monkeypatch
    ):
        # This test specifically exercises the Path.home()-based legacy
        # ~/forge preference path in _resolve_effective_config_dir.
        # FORGE_CONFIG MUST be unset so the home() lookup is reached.
        legacy = tmp_path / "forge"
        legacy.mkdir()
        # Default ~/.forge also exists (the configured default).
        default = tmp_path / ".forge"
        default.mkdir()

        monkeypatch.delenv("FORGE_CONFIG", raising=False)

        # Mock Path.home(). The install pipeline does 3 home() lookups in
        # this scenario (the resolver checks legacy + default, plus one
        # additional lookup elsewhere in the install path). The interleaving
        # of home() and get_mcp_auth_token() is an implementation detail of
        # the install pipeline, so we assert order-independently using
        # tripwire.in_any_order() (the tripwire/tripwire-blessed escape hatch
        # for "interactions occurred but the relative ordering is incidental").
        #
        # We pin EXPECTED_HOME_CALLS rather than draining: if the resolver
        # ever stops calling home() (e.g. caches the result), the test must
        # fail loudly rather than silently pass with zero asserts. tripwire's
        # MethodProxy.assert_call() asserts one interaction at a time; there
        # is no times=N parameter (verified against
        # tripwire/_mock_plugin.py:130-158).
        EXPECTED_HOME_CALLS = 3
        m_home = tripwire.mock("pathlib:Path.home")
        for _ in range(EXPECTED_HOME_CALLS):
            m_home.returns(tmp_path)
        m_token = tripwire.mock(f"{FC_MOD}:get_mcp_auth_token").returns(TEST_TOKEN)

        installer = _make_installer(spellbook_dir, default)
        with tripwire:
            installer.install()

        with tripwire.in_any_order():
            for _ in range(EXPECTED_HOME_CALLS):
                m_home.assert_call()
            m_token.assert_call()

        legacy_actual = json.loads((legacy / ".mcp.json").read_text(encoding="utf-8"))
        assert legacy_actual == {"mcpServers": {"spellbook": _expected_spellbook_entry()}}
        # Default dir is left untouched.
        assert not (default / ".mcp.json").exists()
        assert not (default / "AGENTS.md").exists()

    def test_install_merges_existing_mcp_json_preserving_other_servers(
        self, spellbook_dir, forge_config_dir, forge_env
    ):
        existing = {
            "mcpServers": {
                "foo": {"url": "http://other:9999/mcp", "oauth": True},
            }
        }
        mcp_path = forge_config_dir / ".mcp.json"
        mcp_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

        m_token = tripwire.mock(f"{FC_MOD}:get_mcp_auth_token").returns(TEST_TOKEN)
        installer = _make_installer(spellbook_dir, forge_config_dir)
        with tripwire:
            installer.install()
        m_token.assert_call()

        actual = json.loads(mcp_path.read_text(encoding="utf-8"))
        assert actual == {
            "mcpServers": {
                "foo": {"url": "http://other:9999/mcp", "oauth": True},
                "spellbook": _expected_spellbook_entry(),
            }
        }

    def test_install_demarcation_preserves_existing_AGENTS_md(
        self, spellbook_dir, forge_config_dir, forge_env
    ):
        agents_md = forge_config_dir / "AGENTS.md"
        user_content = "# user content\n\nMy own rules here.\n"
        agents_md.write_text(user_content, encoding="utf-8")

        m_token = tripwire.mock(f"{FC_MOD}:get_mcp_auth_token").returns(TEST_TOKEN)
        installer = _make_installer(spellbook_dir, forge_config_dir)
        with tripwire:
            installer.install()
        m_token.assert_call()

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
        self, spellbook_dir, forge_config_dir, monkeypatch, tmp_path
    ):
        # This test specifically exercises the FORGE_CONFIG-unset branch and
        # the env_warning emission. Path.home() is reached because the resolver
        # checks legacy ~/forge / default ~/.forge.
        monkeypatch.delenv("FORGE_CONFIG", raising=False)

        # Mock Path.home(). With no pre-existing legacy ~/forge directory
        # the resolver short-circuits earlier than the legacy-preference
        # test: 3 home() calls total in this install path. See the legacy
        # test for the full rationale on pinning the exact count and using
        # in_any_order() instead of draining.
        EXPECTED_HOME_CALLS = 3
        m_home = tripwire.mock("pathlib:Path.home")
        for _ in range(EXPECTED_HOME_CALLS):
            m_home.returns(tmp_path)
        m_token = tripwire.mock(f"{FC_MOD}:get_mcp_auth_token").returns(TEST_TOKEN)

        # Real install (NOT dry_run) so the env_warning gating runs.
        installer = _make_installer(spellbook_dir, forge_config_dir, dry_run=False)
        with tripwire:
            results = installer.install()

        with tripwire.in_any_order():
            for _ in range(EXPECTED_HOME_CALLS):
                m_home.assert_call()
            m_token.assert_call()

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
        self, spellbook_dir, forge_config_dir, forge_env
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

        # uninstall does NOT call get_mcp_auth_token; no mock needed for it.
        installer = _make_installer(spellbook_dir, forge_config_dir)
        with tripwire:
            installer.uninstall()

        actual = json.loads(mcp_path.read_text(encoding="utf-8"))
        assert actual == {
            "mcpServers": {
                "foo": {"url": "http://other:9999/mcp", "oauth": True},
            }
        }

    def test_mcp_server_name_collision_overwrites(
        self, spellbook_dir, forge_config_dir, forge_env
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

        m_token = tripwire.mock(f"{FC_MOD}:get_mcp_auth_token").returns(TEST_TOKEN)
        installer = _make_installer(spellbook_dir, forge_config_dir)
        with tripwire:
            installer.install()
        m_token.assert_call()

        actual = json.loads(mcp_path.read_text(encoding="utf-8"))
        assert actual == {"mcpServers": {"spellbook": _expected_spellbook_entry()}}

    def test_install_with_invalid_FORGE_CONFIG_path_skips(
        self, spellbook_dir, tmp_path, monkeypatch
    ):
        bogus = tmp_path / "nonexistent" / "path" / "that" / "does" / "not" / "exist"
        # Note: do NOT mkdir; must remain absent.
        monkeypatch.setenv("FORGE_CONFIG", str(bogus))

        # No get_mcp_auth_token mock: install() short-circuits on missing
        # config_dir before reaching the MCP write path.
        installer = _make_installer(spellbook_dir, bogus)
        with tripwire:
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


class TestForgeCodeDetect:
    """detect() coverage across the four config-dir states.

    All tests pin ``FORGE_CONFIG`` via ``monkeypatch.setenv`` so the resolver
    short-circuits before any ``Path.home()`` lookup; the temp config dir IS
    the effective config dir. Assertions construct the full expected
    ``PlatformStatus`` instance and compare with ``==`` (Level 4-5).
    """

    def test_detect_clean_environment(
        self, spellbook_dir, tmp_path, monkeypatch
    ):
        # Config dir does NOT exist; resolver returns the unchanged path.
        missing = tmp_path / "missing-forge"
        monkeypatch.setenv("FORGE_CONFIG", str(missing))

        installer = _make_installer(spellbook_dir, missing)
        with tripwire:
            status = installer.detect()

        expected = fc_mod.PlatformStatus(
            platform="forgecode",
            available=False,
            installed=False,
            version=None,
            details={
                "config_dir": str(missing),
                "mcp_registered": False,
                "mcp_config": str(missing / ".mcp.json"),
            },
        )
        assert status == expected

    def test_detect_with_only_AGENTS_md(
        self, spellbook_dir, forge_config_dir, forge_env
    ):
        # Plain user AGENTS.md (no spellbook demarcation) and no .mcp.json.
        agents_md = forge_config_dir / "AGENTS.md"
        agents_md.write_text("# user content\n", encoding="utf-8")

        installer = _make_installer(spellbook_dir, forge_config_dir)
        with tripwire:
            status = installer.detect()

        expected = fc_mod.PlatformStatus(
            platform="forgecode",
            available=True,
            installed=False,
            version=None,
            details={
                "config_dir": str(forge_config_dir),
                "mcp_registered": False,
                "mcp_config": str(forge_config_dir / ".mcp.json"),
            },
        )
        assert status == expected

    def test_detect_with_only_mcp_json(
        self, spellbook_dir, forge_config_dir, forge_env
    ):
        # .mcp.json with spellbook entry exists; AGENTS.md does not.
        mcp_path = forge_config_dir / ".mcp.json"
        mcp_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "spellbook": {
                            "url": DAEMON_URL,
                            "oauth": False,
                            "headers": {"Authorization": f"Bearer {TEST_TOKEN}"},
                        }
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        installer = _make_installer(spellbook_dir, forge_config_dir)
        with tripwire:
            status = installer.detect()

        expected = fc_mod.PlatformStatus(
            platform="forgecode",
            available=True,
            installed=True,
            version=None,
            details={
                "config_dir": str(forge_config_dir),
                "mcp_registered": True,
                "mcp_config": str(mcp_path),
            },
        )
        assert status == expected

    def test_detect_with_both_files(
        self, spellbook_dir, forge_config_dir, forge_env
    ):
        # Run a real install to create both files in canonical form, then detect.
        m_token = tripwire.mock(f"{FC_MOD}:get_mcp_auth_token").returns(TEST_TOKEN)
        installer = _make_installer(spellbook_dir, forge_config_dir)
        with tripwire:
            installer.install()
            status = installer.detect()
        m_token.assert_call()

        expected = fc_mod.PlatformStatus(
            platform="forgecode",
            available=True,
            installed=True,
            version=TEST_VERSION,
            details={
                "config_dir": str(forge_config_dir),
                "mcp_registered": True,
                "mcp_config": str(forge_config_dir / ".mcp.json"),
            },
        )
        assert status == expected


class TestForgeCodeInCore:
    """Verify ForgeCodeInstaller is registered in the core dispatcher."""

    def test_get_platform_installer_returns_forgecode(
        self, spellbook_dir, tmp_path, monkeypatch
    ):
        from installer.core import get_platform_installer

        # Set FORGE_CONFIG to bypass Path.home() lookup in resolve_config_dirs.
        monkeypatch.setenv("FORGE_CONFIG", str(tmp_path / ".forge"))
        installer = get_platform_installer(
            "forgecode", spellbook_dir, TEST_VERSION, dry_run=True
        )
        assert isinstance(installer, ForgeCodeInstaller)
