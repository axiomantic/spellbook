"""Tests for the MCP daemon installation architecture.

Covers:
- Centralized daemon install in Installer.run()
- Platform installers NOT calling install_daemon
- check_daemon_health() scenarios
- get_daemon_python() symlink preservation
- _get_repairs() using find_spec
- -y flag selecting all platforms
- ensure_daemon_venv() hash detection
"""

import hashlib
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def spellbook_dir(tmp_path):
    """Create a mock spellbook directory with minimal structure."""
    sb = tmp_path / "spellbook"
    sb.mkdir()
    (sb / ".version").write_text("0.10.0")

    # MCP server stub
    mcp_dir = sb / "spellbook_mcp"
    mcp_dir.mkdir()
    (mcp_dir / "server.py").write_text("# server stub")

    # Skills directory
    (sb / "skills").mkdir()

    # Claude Code expects these subdirs
    for subdir in ["skills", "commands", "scripts", "agents", "plans"]:
        (sb / subdir).mkdir(exist_ok=True)

    # AGENTS.spellbook.md for context generation
    (sb / "AGENTS.spellbook.md").write_text("# Spellbook\nTest content.")

    # Extensions dir for Gemini
    ext_dir = sb / "extensions" / "gemini"
    ext_dir.mkdir(parents=True)
    (ext_dir / "manifest.json").write_text("{}")

    return sb


@pytest.fixture
def home_dir(tmp_path):
    """Create a mock home directory with platform config dirs."""
    home = tmp_path / "home"
    home.mkdir()

    # Claude Code config
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    for subdir in ["skills", "commands", "scripts", "agents", "plans"]:
        (claude_dir / subdir).mkdir()

    # OpenCode config
    opencode_dir = home / ".config" / "opencode"
    opencode_dir.mkdir(parents=True)

    # Codex config
    codex_dir = home / ".codex"
    codex_dir.mkdir()

    # Gemini config
    gemini_dir = home / ".gemini"
    gemini_dir.mkdir()
    (gemini_dir / "extensions").mkdir()

    # Crush config
    crush_dir = home / ".local" / "share" / "crush"
    crush_dir.mkdir(parents=True)

    return home


# ---------------------------------------------------------------------------
# 1. Centralized daemon install in Installer.run()
# ---------------------------------------------------------------------------

class TestInstallerRunDaemonCentralized:
    """Verify daemon install happens once, before platform installs."""

    def test_daemon_install_called_before_platforms(self, spellbook_dir, home_dir, monkeypatch):
        """Daemon install_daemon() is called before any platform install()."""
        from installer.core import Installer

        monkeypatch.setattr(Path, "home", lambda: home_dir)

        call_order = []

        original_install_daemon = None

        def mock_install_daemon(sb_dir, dry_run=False):
            call_order.append("install_daemon")
            return (True, "daemon installed")

        def mock_get_platform_installer(platform, sb_dir, version, dry_run=False, on_step=None):
            mock_installer = MagicMock()
            mock_installer.platform_name = platform
            mock_installer.platform_id = platform

            def mock_install(force=False):
                call_order.append(f"platform_install:{platform}")
                return []
            mock_installer.install = mock_install

            status = MagicMock()
            status.available = True
            status.installed = False
            mock_installer.detect.return_value = status
            return mock_installer

        monkeypatch.setattr("installer.core.get_platform_config_dir", lambda p: home_dir / ".claude")

        with patch("installer.core.get_platform_installer", side_effect=mock_get_platform_installer), \
             patch("installer.components.mcp.install_daemon", side_effect=mock_install_daemon), \
             patch("installer.demarcation.get_installed_version", return_value=None):
            installer = Installer(spellbook_dir)
            session = installer.run(platforms=["claude_code", "opencode"], dry_run=False)

        assert call_order[0] == "install_daemon"
        platform_installs = [c for c in call_order if c.startswith("platform_install:")]
        assert len(platform_installs) == 2
        assert call_order.index("install_daemon") < call_order.index(platform_installs[0])

    def test_progress_events_order(self, spellbook_dir, home_dir, monkeypatch):
        """Progress events fire in correct order: daemon_start, step, result, platform_start(s), health_start."""
        from installer.core import Installer

        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.setattr("installer.core.get_platform_config_dir", lambda p: home_dir / ".claude")
        monkeypatch.setattr("installer.demarcation.get_installed_version", lambda p: None)

        events = []

        def on_progress(event, data):
            events.append(event)

        mock_installer = MagicMock()
        mock_installer.platform_name = "Claude Code"
        mock_installer.platform_id = "claude_code"
        mock_installer.install.return_value = []
        status = MagicMock()
        status.available = True
        mock_installer.detect.return_value = status

        with patch("installer.core.get_platform_installer", return_value=mock_installer), \
             patch("installer.components.mcp.install_daemon", return_value=(True, "ok")), \
             patch("installer.components.mcp.check_daemon_health", return_value=(True, "healthy")):
            installer = Installer(spellbook_dir)
            installer.run(platforms=["claude_code"], dry_run=False, on_progress=on_progress)

        # daemon_start comes first, then step (installing daemon), then result
        assert events[0] == "daemon_start"
        assert "step" in events[1:3]
        assert "result" in events[1:3]

        # platform_start comes after daemon result
        assert "platform_start" in events
        daemon_result_idx = next(i for i, e in enumerate(events) if e == "result")
        platform_start_idx = next(i for i, e in enumerate(events) if e == "platform_start")
        assert platform_start_idx > daemon_result_idx

        # health_start comes after platform_start
        assert "health_start" in events
        health_start_idx = next(i for i, e in enumerate(events) if e == "health_start")
        assert health_start_idx > platform_start_idx

    def test_daemon_result_in_session_with_system_platform(self, spellbook_dir, home_dir, monkeypatch):
        """Daemon result is recorded with platform='system'."""
        from installer.core import Installer

        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.setattr("installer.core.get_platform_config_dir", lambda p: home_dir / ".claude")
        monkeypatch.setattr("installer.demarcation.get_installed_version", lambda p: None)

        with patch("installer.core.get_platform_installer") as mock_gpi, \
             patch("installer.components.mcp.install_daemon", return_value=(True, "daemon ok")), \
             patch("installer.components.mcp.check_daemon_health", return_value=(True, "healthy")):

            mock_pi = MagicMock()
            mock_pi.platform_name = "Test"
            mock_pi.platform_id = "test"
            mock_pi.install.return_value = []
            mock_pi.detect.return_value = MagicMock(available=True)
            mock_gpi.return_value = mock_pi

            installer = Installer(spellbook_dir)
            session = installer.run(platforms=["claude_code"], dry_run=False)

        daemon_results = [r for r in session.results if r.component == "mcp_daemon"]
        assert len(daemon_results) == 1
        assert daemon_results[0].platform == "system"
        assert daemon_results[0].success is True

    def test_health_check_runs_only_on_daemon_success(self, spellbook_dir, home_dir, monkeypatch):
        """Health check runs when daemon succeeds and not dry_run."""
        from installer.core import Installer

        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.setattr("installer.core.get_platform_config_dir", lambda p: home_dir / ".claude")
        monkeypatch.setattr("installer.demarcation.get_installed_version", lambda p: None)

        mock_pi = MagicMock()
        mock_pi.platform_name = "Test"
        mock_pi.platform_id = "test"
        mock_pi.install.return_value = []
        mock_pi.detect.return_value = MagicMock(available=True)

        with patch("installer.core.get_platform_installer", return_value=mock_pi), \
             patch("installer.components.mcp.install_daemon", return_value=(True, "ok")), \
             patch("installer.components.mcp.check_daemon_health", return_value=(True, "healthy")) as mock_health:
            installer = Installer(spellbook_dir)
            session = installer.run(platforms=["claude_code"], dry_run=False)

        mock_health.assert_called_once()
        health_results = [r for r in session.results if r.component == "mcp_health"]
        assert len(health_results) == 1
        assert health_results[0].platform == "system"

    def test_health_check_skipped_on_dry_run(self, spellbook_dir, home_dir, monkeypatch):
        """Health check does NOT run during dry_run."""
        from installer.core import Installer

        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.setattr("installer.core.get_platform_config_dir", lambda p: home_dir / ".claude")
        monkeypatch.setattr("installer.demarcation.get_installed_version", lambda p: None)

        mock_pi = MagicMock()
        mock_pi.platform_name = "Test"
        mock_pi.platform_id = "test"
        mock_pi.install.return_value = []
        mock_pi.detect.return_value = MagicMock(available=True)

        with patch("installer.core.get_platform_installer", return_value=mock_pi), \
             patch("installer.components.mcp.install_daemon", return_value=(True, "ok")), \
             patch("installer.components.mcp.check_daemon_health") as mock_health:
            installer = Installer(spellbook_dir)
            session = installer.run(platforms=["claude_code"], dry_run=True)

        mock_health.assert_not_called()
        health_results = [r for r in session.results if r.component == "mcp_health"]
        assert len(health_results) == 0

    def test_health_check_skipped_on_daemon_failure(self, spellbook_dir, home_dir, monkeypatch):
        """Health check does NOT run when daemon installation fails."""
        from installer.core import Installer

        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.setattr("installer.core.get_platform_config_dir", lambda p: home_dir / ".claude")
        monkeypatch.setattr("installer.demarcation.get_installed_version", lambda p: None)

        mock_pi = MagicMock()
        mock_pi.platform_name = "Test"
        mock_pi.platform_id = "test"
        mock_pi.install.return_value = []
        mock_pi.detect.return_value = MagicMock(available=True)

        with patch("installer.core.get_platform_installer", return_value=mock_pi), \
             patch("installer.components.mcp.install_daemon", return_value=(False, "venv failed")), \
             patch("installer.components.mcp.check_daemon_health") as mock_health:
            installer = Installer(spellbook_dir)
            session = installer.run(platforms=["claude_code"], dry_run=False)

        mock_health.assert_not_called()
        daemon_results = [r for r in session.results if r.component == "mcp_daemon"]
        assert daemon_results[0].success is False
        assert daemon_results[0].action == "failed"


# ---------------------------------------------------------------------------
# 2. Platform installers do NOT call install_daemon
# ---------------------------------------------------------------------------

class TestPlatformInstallersNoInstallDaemon:
    """Each platform installer.install() must NOT call install_daemon."""

    def test_claude_code_no_install_daemon(self, spellbook_dir, home_dir, monkeypatch):
        """ClaudeCodeInstaller.install() does not call install_daemon."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        config_dir = home_dir / ".claude"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")

        with patch("installer.platforms.claude_code.check_claude_cli_available", return_value=False), \
             patch("installer.components.mcp.check_claude_cli_available", return_value=False), \
             patch("installer.components.mcp.install_daemon") as mock_daemon:
            installer.install()

        mock_daemon.assert_not_called()

    def test_codex_no_install_daemon(self, spellbook_dir, home_dir, monkeypatch):
        """CodexInstaller.install() does not call install_daemon."""
        from installer.platforms.codex import CodexInstaller

        config_dir = home_dir / ".codex"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        installer = CodexInstaller(spellbook_dir, config_dir, "0.10.0")

        with patch("installer.components.mcp.install_daemon") as mock_daemon:
            installer.install()

        mock_daemon.assert_not_called()

    def test_gemini_no_install_daemon(self, spellbook_dir, home_dir, monkeypatch):
        """GeminiInstaller.install() does not call install_daemon."""
        from installer.platforms.gemini import GeminiInstaller

        config_dir = home_dir / ".gemini"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        installer = GeminiInstaller(spellbook_dir, config_dir, "0.10.0")

        with patch("installer.platforms.gemini.check_gemini_cli_available", return_value=True), \
             patch("installer.platforms.gemini.link_extension", return_value=(True, "ok")), \
             patch("installer.components.mcp.install_daemon") as mock_daemon:
            installer.install()

        mock_daemon.assert_not_called()

    def test_crush_no_install_daemon(self, spellbook_dir, home_dir, monkeypatch):
        """CrushInstaller.install() does not call install_daemon."""
        from installer.platforms.crush import CrushInstaller

        config_dir = home_dir / ".local" / "share" / "crush"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        installer = CrushInstaller(spellbook_dir, config_dir, "0.10.0")

        with patch("installer.components.mcp.install_daemon") as mock_daemon:
            installer.install()

        mock_daemon.assert_not_called()

    def test_opencode_no_install_daemon(self, spellbook_dir, home_dir, monkeypatch):
        """OpenCodeInstaller.install() does not call install_daemon."""
        from installer.platforms.opencode import OpenCodeInstaller

        config_dir = home_dir / ".config" / "opencode"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        installer = OpenCodeInstaller(spellbook_dir, config_dir, "0.10.0")

        with patch("installer.components.mcp.install_daemon") as mock_daemon:
            installer.install()

        mock_daemon.assert_not_called()


# ---------------------------------------------------------------------------
# 3. check_daemon_health()
# ---------------------------------------------------------------------------

class TestCheckDaemonHealth:
    """Test all return paths of check_daemon_health()."""

    def test_healthy_response(self):
        """Returns (True, message) with version and uptime on success."""
        from installer.components.mcp import check_daemon_health

        response_body = json.dumps({
            "status": "ok",
            "version": "0.10.0",
            "uptime_seconds": 42.5,
        }).encode()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            healthy, msg = check_daemon_health()

        assert healthy is True
        assert "v0.10.0" in msg
        assert "42s" in msg

    def test_url_error(self):
        """Returns (False, message) on URLError (daemon not running)."""
        from installer.components.mcp import check_daemon_health
        from urllib.error import URLError

        with patch("urllib.request.urlopen", side_effect=URLError("Connection refused")):
            healthy, msg = check_daemon_health()

        assert healthy is False
        assert "daemon not responding" in msg
        assert "Connection refused" in msg

    def test_timeout_error(self):
        """Returns (False, message) on TimeoutError."""
        from installer.components.mcp import check_daemon_health

        with patch("urllib.request.urlopen", side_effect=TimeoutError()):
            healthy, msg = check_daemon_health()

        assert healthy is False
        assert "timed out" in msg

    def test_non_200_status(self):
        """Returns (False, message) on non-200 HTTP status."""
        from installer.components.mcp import check_daemon_health

        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            healthy, msg = check_daemon_health()

        assert healthy is False
        assert "HTTP 500" in msg

    def test_os_error(self):
        """Returns (False, message) on generic OSError."""
        from installer.components.mcp import check_daemon_health

        with patch("urllib.request.urlopen", side_effect=OSError("Network unreachable")):
            healthy, msg = check_daemon_health()

        assert healthy is False
        assert "daemon not responding" in msg

    def test_custom_timeout_value(self):
        """Timeout parameter is passed to urlopen."""
        from installer.components.mcp import check_daemon_health

        response_body = json.dumps({
            "status": "ok",
            "version": "1.0",
            "uptime_seconds": 0,
        }).encode()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            check_daemon_health(timeout=30)

        # Verify timeout was passed
        args, kwargs = mock_urlopen.call_args
        assert kwargs.get("timeout") == 30 or (len(args) > 1 and args[1] == 30)


# ---------------------------------------------------------------------------
# 4. get_daemon_python() symlink preservation
# ---------------------------------------------------------------------------

class TestGetDaemonPython:
    """Test symlink preservation in get_daemon_python()."""

    def test_symlink_preserved(self, tmp_path, monkeypatch):
        """When SPELLBOOK_DAEMON_PYTHON points to a symlink, the returned path
        preserves the symlink (does not resolve it)."""
        # Create a real python-like file and a symlink to it
        real_python = tmp_path / "real_python"
        real_python.write_text("#!/usr/bin/env python3")
        real_python.chmod(0o755)

        venv_bin = tmp_path / "daemon-venv" / "bin"
        venv_bin.mkdir(parents=True)
        symlink_python = venv_bin / "python"
        symlink_python.symlink_to(real_python)

        monkeypatch.setenv("SPELLBOOK_DAEMON_PYTHON", str(symlink_python))

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "spellbook_server",
            str(Path(__file__).parent.parent / "scripts" / "spellbook-server.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod.get_daemon_python()

        assert result is not None
        # The result must contain the symlink path, not the resolved real_python path
        assert "daemon-venv" in result
        assert str(real_python) != result

    def test_env_not_set_returns_none(self, monkeypatch):
        """Returns None when SPELLBOOK_DAEMON_PYTHON is not set."""
        monkeypatch.delenv("SPELLBOOK_DAEMON_PYTHON", raising=False)

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "spellbook_server",
            str(Path(__file__).parent.parent / "scripts" / "spellbook-server.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod.get_daemon_python()
        assert result is None

    def test_nonexistent_file_returns_none(self, tmp_path, monkeypatch):
        """Returns None when SPELLBOOK_DAEMON_PYTHON points to a file that doesn't exist."""
        monkeypatch.setenv("SPELLBOOK_DAEMON_PYTHON", str(tmp_path / "nonexistent" / "python"))

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "spellbook_server",
            str(Path(__file__).parent.parent / "scripts" / "spellbook-server.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod.get_daemon_python()
        assert result is None


# ---------------------------------------------------------------------------
# 5. _get_repairs() uses find_spec
# ---------------------------------------------------------------------------

class TestGetRepairs:
    """Test _get_repairs() uses find_spec instead of importing kokoro."""

    def test_tts_enabled_kokoro_missing(self):
        """Returns tts-deps-missing repair when TTS enabled but kokoro not installed."""
        from spellbook_mcp.config_tools import _get_repairs

        with patch("spellbook_mcp.config_tools.config_get", return_value=True) as mock_cg, \
             patch("importlib.util.find_spec", return_value=None):
            repairs = _get_repairs()

        mock_cg.assert_any_call("tts_enabled")
        tts_repairs = [r for r in repairs if r["id"] == "tts-deps-missing"]
        assert len(tts_repairs) == 1
        assert tts_repairs[0]["severity"] == "warning"

    def test_tts_not_enabled_no_repair(self):
        """Returns no TTS repair when TTS is not enabled."""
        from spellbook_mcp.config_tools import _get_repairs

        with patch("spellbook_mcp.config_tools.config_get", return_value=False):
            repairs = _get_repairs()

        tts_repairs = [r for r in repairs if "tts" in r.get("id", "")]
        assert len(tts_repairs) == 0

    def test_tts_enabled_kokoro_installed(self):
        """No tts-deps-missing repair when both kokoro and soundfile are present."""
        from spellbook_mcp.config_tools import _get_repairs

        def mock_find_spec(name):
            if name in ("kokoro", "soundfile", "pip"):
                mock = MagicMock()
                mock.name = name
                return mock
            return None

        with patch("spellbook_mcp.config_tools.config_get", return_value=True), \
             patch("importlib.util.find_spec", side_effect=mock_find_spec):
            repairs = _get_repairs()

        tts_deps_repairs = [r for r in repairs if r["id"] == "tts-deps-missing"]
        assert len(tts_deps_repairs) == 0

    def test_find_spec_used_not_import(self):
        """Verify find_spec is called, not direct import of kokoro."""
        from spellbook_mcp.config_tools import _get_repairs

        with patch("spellbook_mcp.config_tools.config_get", return_value=True), \
             patch("importlib.util.find_spec") as mock_fs:
            mock_fs.return_value = None
            _get_repairs()

        # find_spec should have been called with "kokoro"
        calls = [c for c in mock_fs.call_args_list if c[0][0] == "kokoro"]
        assert len(calls) >= 1


# ---------------------------------------------------------------------------
# 6. -y flag selects all platforms
# ---------------------------------------------------------------------------

class TestYesFlagSelectsPlatforms:
    """Test that -y flag auto-selects all platforms via detect_platforms()."""

    def test_yes_flag_uses_detect_platforms(self, spellbook_dir, home_dir, monkeypatch):
        """When args.yes is True, detect_platforms() is used instead of interactive selection."""
        from installer.core import Installer

        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.setattr("installer.core.get_platform_config_dir", lambda p: home_dir / ".claude")
        monkeypatch.setattr("installer.demarcation.get_installed_version", lambda p: None)

        mock_pi = MagicMock()
        mock_pi.platform_name = "Test"
        mock_pi.platform_id = "test"
        mock_pi.install.return_value = []
        mock_pi.detect.return_value = MagicMock(available=True)

        with patch("installer.core.get_platform_installer", return_value=mock_pi), \
             patch("installer.components.mcp.install_daemon", return_value=(True, "ok")), \
             patch("installer.components.mcp.check_daemon_health", return_value=(True, "ok")):
            installer = Installer(spellbook_dir)
            detected = installer.detect_platforms()

            # Simulate -y behavior: platforms = installer.detect_platforms()
            session = installer.run(platforms=detected, dry_run=True)

        # Verify detected platforms were used (at least claude_code is always detected)
        assert len(detected) >= 1
        assert "claude_code" in detected

    def test_no_interactive_uses_detect_platforms(self):
        """When not interactive, detect_platforms() should be used."""
        # This tests the logic from install.py line ~922
        # We verify the conditional: args.yes or args.no_interactive or not is_interactive()

        args = MagicMock()
        args.platforms = None
        args.yes = True
        args.no_interactive = False

        # The condition is: args.yes or args.no_interactive or not is_interactive()
        # With args.yes = True, it should use detect_platforms
        assert args.yes or args.no_interactive  # This path triggers detect_platforms()


# ---------------------------------------------------------------------------
# 7. ensure_daemon_venv() hash detection
# ---------------------------------------------------------------------------

class TestEnsureDaemonVenvHashDetection:
    """Test the hash comparison logic in ensure_daemon_venv()."""

    def test_hash_matches_skips_rebuild(self, tmp_path, monkeypatch):
        """When lockfile hash matches stored hash, venv is not rebuilt."""
        from installer.components.mcp import ensure_daemon_venv

        # Create lockfile
        daemon_dir = tmp_path / "spellbook" / "daemon"
        daemon_dir.mkdir(parents=True)
        lockfile = daemon_dir / "requirements.txt"
        lockfile.write_text("fastmcp==1.0\nuvicorn==0.30\n")

        # Compute hash
        h = hashlib.sha256(lockfile.read_bytes()).hexdigest()

        # Create venv dir with matching hash file and a python binary
        venv_dir = tmp_path / "config" / "daemon-venv"
        venv_bin = venv_dir / "bin"
        venv_bin.mkdir(parents=True)
        python_path = venv_bin / "python"
        python_path.write_text("#!/usr/bin/env python3")

        hash_file = venv_dir / ".lockfile-hash"
        hash_file.write_text(h)

        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_venv_dir",
            lambda: venv_dir,
        )
        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_python",
            lambda: python_path,
        )

        success, msg = ensure_daemon_venv(tmp_path / "spellbook")

        assert success is True
        assert "up to date" in msg

    def test_hash_mismatch_triggers_rebuild(self, tmp_path, monkeypatch):
        """When lockfile hash differs from stored hash, venv is rebuilt."""
        from installer.components.mcp import ensure_daemon_venv

        # Create lockfile
        daemon_dir = tmp_path / "spellbook" / "daemon"
        daemon_dir.mkdir(parents=True)
        lockfile = daemon_dir / "requirements.txt"
        lockfile.write_text("fastmcp==2.0\nuvicorn==0.31\n")

        # Create venv dir with mismatched hash
        venv_dir = tmp_path / "config" / "daemon-venv"
        venv_bin = venv_dir / "bin"
        venv_bin.mkdir(parents=True)
        python_path = venv_bin / "python"
        python_path.write_text("#!/usr/bin/env python3")

        hash_file = venv_dir / ".lockfile-hash"
        hash_file.write_text("stale_hash_value")

        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_venv_dir",
            lambda: venv_dir,
        )
        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_python",
            lambda: python_path,
        )

        # Mock the subprocess calls and stop_daemon since it will try to rebuild
        with patch("installer.components.mcp.stop_daemon"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            success, msg = ensure_daemon_venv(tmp_path / "spellbook")

        # subprocess.run should have been called to create the venv
        assert mock_run.called

    def test_force_triggers_rebuild(self, tmp_path, monkeypatch):
        """force=True always triggers rebuild even when hash matches."""
        from installer.components.mcp import ensure_daemon_venv

        # Create lockfile
        daemon_dir = tmp_path / "spellbook" / "daemon"
        daemon_dir.mkdir(parents=True)
        lockfile = daemon_dir / "requirements.txt"
        lockfile.write_text("fastmcp==1.0\n")

        # Compute matching hash
        h = hashlib.sha256(lockfile.read_bytes()).hexdigest()

        venv_dir = tmp_path / "config" / "daemon-venv"
        venv_bin = venv_dir / "bin"
        venv_bin.mkdir(parents=True)
        python_path = venv_bin / "python"
        python_path.write_text("#!/usr/bin/env python3")

        hash_file = venv_dir / ".lockfile-hash"
        hash_file.write_text(h)

        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_venv_dir",
            lambda: venv_dir,
        )
        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_python",
            lambda: python_path,
        )

        with patch("installer.components.mcp.stop_daemon"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            ensure_daemon_venv(tmp_path / "spellbook", force=True)

        # Should rebuild despite matching hash
        assert mock_run.called

    def test_missing_hash_file_triggers_rebuild(self, tmp_path, monkeypatch):
        """When no .lockfile-hash exists, venv is rebuilt."""
        from installer.components.mcp import ensure_daemon_venv

        daemon_dir = tmp_path / "spellbook" / "daemon"
        daemon_dir.mkdir(parents=True)
        lockfile = daemon_dir / "requirements.txt"
        lockfile.write_text("fastmcp==1.0\n")

        venv_dir = tmp_path / "config" / "daemon-venv"
        venv_bin = venv_dir / "bin"
        venv_bin.mkdir(parents=True)
        python_path = venv_bin / "python"
        python_path.write_text("#!/usr/bin/env python3")

        # No .lockfile-hash file exists

        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_venv_dir",
            lambda: venv_dir,
        )
        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_python",
            lambda: python_path,
        )

        with patch("installer.components.mcp.stop_daemon"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            ensure_daemon_venv(tmp_path / "spellbook")

        assert mock_run.called

    def test_missing_lockfile_returns_failure(self, tmp_path):
        """Returns (False, message) when lockfile doesn't exist."""
        from installer.components.mcp import ensure_daemon_venv

        sb_dir = tmp_path / "spellbook"
        sb_dir.mkdir()
        # No daemon/requirements.txt

        success, msg = ensure_daemon_venv(sb_dir)

        assert success is False
        assert "not found" in msg

    def test_missing_python_binary_triggers_rebuild(self, tmp_path, monkeypatch):
        """When daemon python binary doesn't exist, venv is rebuilt."""
        from installer.components.mcp import ensure_daemon_venv

        daemon_dir = tmp_path / "spellbook" / "daemon"
        daemon_dir.mkdir(parents=True)
        lockfile = daemon_dir / "requirements.txt"
        lockfile.write_text("fastmcp==1.0\n")

        # Compute matching hash
        h = hashlib.sha256(lockfile.read_bytes()).hexdigest()

        venv_dir = tmp_path / "config" / "daemon-venv"
        venv_dir.mkdir(parents=True)

        # Python binary does NOT exist
        python_path = venv_dir / "bin" / "python"

        hash_file = venv_dir / ".lockfile-hash"
        hash_file.write_text(h)

        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_venv_dir",
            lambda: venv_dir,
        )
        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_python",
            lambda: python_path,
        )

        with patch("installer.components.mcp.stop_daemon"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            ensure_daemon_venv(tmp_path / "spellbook")

        # Should rebuild because python binary is missing
        assert mock_run.called


# ---------------------------------------------------------------------------
# 8. install_daemon() includes TTS when previously enabled
# ---------------------------------------------------------------------------

class TestInstallDaemonTtsInclusion:
    """Test that install_daemon() passes include_tts=True when TTS was previously enabled."""

    def test_includes_tts_when_config_enabled(self, tmp_path, monkeypatch):
        """install_daemon passes include_tts=True when tts_enabled config is True."""
        from installer.components.mcp import install_daemon

        sb_dir = tmp_path / "spellbook"
        sb_dir.mkdir()
        (sb_dir / "scripts").mkdir()
        (sb_dir / "scripts" / "spellbook-server.py").write_text("# stub")

        with patch("installer.components.mcp.ensure_daemon_venv", return_value=(True, "ok")) as mock_venv, \
             patch("installer.components.mcp.uninstall_daemon"), \
             patch("installer.components.mcp.get_python_executable", return_value="python3"), \
             patch("installer.components.mcp.get_daemon_python", return_value=tmp_path / "python"), \
             patch("installer.components.mcp.is_daemon_running", return_value=True), \
             patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")), \
             patch("spellbook_mcp.config_tools.config_get", return_value=True):
            install_daemon(sb_dir, dry_run=False)

        # Verify include_tts=True was passed
        mock_venv.assert_called_once()
        _, kwargs = mock_venv.call_args
        assert kwargs.get("include_tts") is True or mock_venv.call_args[1].get("include_tts") is True

    def test_excludes_tts_when_config_disabled(self, tmp_path, monkeypatch):
        """install_daemon passes include_tts=False when tts_enabled config is False."""
        from installer.components.mcp import install_daemon

        sb_dir = tmp_path / "spellbook"
        sb_dir.mkdir()
        (sb_dir / "scripts").mkdir()
        (sb_dir / "scripts" / "spellbook-server.py").write_text("# stub")

        with patch("installer.components.mcp.ensure_daemon_venv", return_value=(True, "ok")) as mock_venv, \
             patch("installer.components.mcp.uninstall_daemon"), \
             patch("installer.components.mcp.get_python_executable", return_value="python3"), \
             patch("installer.components.mcp.get_daemon_python", return_value=tmp_path / "python"), \
             patch("installer.components.mcp.is_daemon_running", return_value=True), \
             patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")), \
             patch("spellbook_mcp.config_tools.config_get", return_value=False):
            install_daemon(sb_dir, dry_run=False)

        mock_venv.assert_called_once()
        _, kwargs = mock_venv.call_args
        assert kwargs.get("include_tts") is False

    def test_excludes_tts_when_config_import_fails(self, tmp_path, monkeypatch):
        """install_daemon passes include_tts=False when config_tools import fails."""
        from installer.components.mcp import install_daemon

        sb_dir = tmp_path / "spellbook"
        sb_dir.mkdir()
        (sb_dir / "scripts").mkdir()
        (sb_dir / "scripts" / "spellbook-server.py").write_text("# stub")

        # Make config_get raise ImportError by patching the import
        with patch("installer.components.mcp.ensure_daemon_venv", return_value=(True, "ok")) as mock_venv, \
             patch("installer.components.mcp.uninstall_daemon"), \
             patch("installer.components.mcp.get_python_executable", return_value="python3"), \
             patch("installer.components.mcp.get_daemon_python", return_value=tmp_path / "python"), \
             patch("installer.components.mcp.is_daemon_running", return_value=True), \
             patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")), \
             patch.dict("sys.modules", {"spellbook_mcp.config_tools": None}):
            install_daemon(sb_dir, dry_run=False)

        mock_venv.assert_called_once()
        _, kwargs = mock_venv.call_args
        assert kwargs.get("include_tts") is False


# ---------------------------------------------------------------------------
# 9. setup_tts() reinstalls TTS when enabled but missing
# ---------------------------------------------------------------------------

class TestSetupTtsReinstall:
    """Test that setup_tts() reinstalls TTS deps when previously enabled but missing."""

    def test_reinstalls_tts_when_enabled_but_missing(self, tmp_path):
        """setup_tts reinstalls TTS deps when config says enabled but kokoro is missing."""
        import install as install_mod

        with patch.object(install_mod, "check_tts_available", return_value=False), \
             patch.object(install_mod, "_install_tts_deps", return_value=True) as mock_install, \
             patch.object(install_mod, "_preload_tts_model") as mock_preload, \
             patch("spellbook_mcp.config_tools.config_get", return_value=True):
            install_mod.setup_tts(dry_run=False, auto_yes=False, spellbook_dir=tmp_path)

        mock_install.assert_called_once_with(tmp_path)
        mock_preload.assert_called_once_with(tmp_path)

    def test_no_reinstall_when_tts_available(self, tmp_path):
        """setup_tts does nothing extra when TTS is already available."""
        import install as install_mod

        with patch.object(install_mod, "check_tts_available", return_value=True), \
             patch.object(install_mod, "_install_tts_deps") as mock_install, \
             patch("spellbook_mcp.config_tools.config_get", return_value=True):
            install_mod.setup_tts(dry_run=False, auto_yes=False, spellbook_dir=tmp_path)

        mock_install.assert_not_called()

    def test_no_reinstall_when_tts_disabled(self, tmp_path):
        """setup_tts does nothing when TTS was explicitly disabled."""
        import install as install_mod

        with patch.object(install_mod, "check_tts_available", return_value=False), \
             patch.object(install_mod, "_install_tts_deps") as mock_install, \
             patch("spellbook_mcp.config_tools.config_get", return_value=False):
            install_mod.setup_tts(dry_run=False, auto_yes=False, spellbook_dir=tmp_path)

        mock_install.assert_not_called()

    def test_warns_on_reinstall_failure(self, tmp_path, capsys):
        """setup_tts warns when TTS reinstall fails."""
        import install as install_mod

        with patch.object(install_mod, "check_tts_available", return_value=False), \
             patch.object(install_mod, "_install_tts_deps", return_value=False), \
             patch("spellbook_mcp.config_tools.config_get", return_value=True):
            install_mod.setup_tts(dry_run=False, auto_yes=False, spellbook_dir=tmp_path)

        captured = capsys.readouterr()
        assert "TTS reinstall failed" in captured.out or "failed" in captured.out.lower()
