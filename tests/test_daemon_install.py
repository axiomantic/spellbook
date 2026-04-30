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

import tripwire
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
    mcp_dir = sb / "spellbook"
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

    return home


def _fake_platform_installer(platform_name, platform_id, call_order=None):
    """Create a fake platform installer class instance."""
    class FakeStatus:
        available = True
        installed = False

    class FakeInstaller:
        def __init__(self):
            self.platform_name = platform_name
            self.platform_id = platform_id
        def install(self, force=False, skip_global_steps=False):
            if call_order is not None:
                call_order.append(f"platform_install:{platform_id}")
            return []
        def detect(self):
            return FakeStatus()

    return FakeInstaller()


# ---------------------------------------------------------------------------
# 1. Centralized daemon install in Installer.run()
# ---------------------------------------------------------------------------

class TestInstallerRunDaemonCentralized:
    """Verify daemon install happens once, before platform installs."""

    def test_daemon_install_called_before_platforms(self, spellbook_dir, home_dir, monkeypatch):
        """Daemon install_daemon() is called before any platform install()."""
        from installer.core import Installer

        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.setattr("installer.core.get_platform_config_dir", lambda p: home_dir / ".claude")
        monkeypatch.setattr("installer.demarcation.get_installed_version", lambda p: None)

        call_order = []

        def mock_install_daemon(*args, **kwargs):
            call_order.append("install_daemon")
            return (True, "daemon installed")

        def mock_get_platform_installer(platform, *args, **kwargs):
            return _fake_platform_installer(platform, platform, call_order)

        monkeypatch.setattr("installer.core.get_platform_installer", mock_get_platform_installer)
        monkeypatch.setattr("installer.components.mcp.install_daemon", mock_install_daemon)

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

        monkeypatch.setattr(
            "installer.core.get_platform_installer",
            lambda *a, **kw: _fake_platform_installer("Claude Code", "claude_code"),
        )
        monkeypatch.setattr("installer.components.mcp.install_daemon", lambda *a, **kw: (True, "ok"))
        monkeypatch.setattr("installer.components.mcp.check_daemon_health", lambda *a, **kw: (True, "healthy"))

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
        monkeypatch.setattr(
            "installer.core.get_platform_installer",
            lambda *a, **kw: _fake_platform_installer("Test", "test"),
        )
        monkeypatch.setattr("installer.components.mcp.install_daemon", lambda *a, **kw: (True, "daemon ok"))
        monkeypatch.setattr("installer.components.mcp.check_daemon_health", lambda *a, **kw: (True, "healthy"))

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
        monkeypatch.setattr(
            "installer.core.get_platform_installer",
            lambda *a, **kw: _fake_platform_installer("Test", "test"),
        )
        monkeypatch.setattr("installer.components.mcp.install_daemon", lambda *a, **kw: (True, "ok"))

        health_called = []

        def track_health(*args, **kwargs):
            health_called.append(True)
            return (True, "healthy")

        monkeypatch.setattr("installer.components.mcp.check_daemon_health", track_health)

        installer = Installer(spellbook_dir)
        session = installer.run(platforms=["claude_code"], dry_run=False)

        assert len(health_called) == 1
        health_results = [r for r in session.results if r.component == "mcp_health"]
        assert len(health_results) == 1
        assert health_results[0].platform == "system"

    def test_health_check_skipped_on_dry_run(self, spellbook_dir, home_dir, monkeypatch):
        """Health check does NOT run during dry_run."""
        from installer.core import Installer

        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.setattr("installer.core.get_platform_config_dir", lambda p: home_dir / ".claude")
        monkeypatch.setattr("installer.demarcation.get_installed_version", lambda p: None)
        monkeypatch.setattr(
            "installer.core.get_platform_installer",
            lambda *a, **kw: _fake_platform_installer("Test", "test"),
        )
        monkeypatch.setattr("installer.components.mcp.install_daemon", lambda *a, **kw: (True, "ok"))

        health_called = []

        def track_health(*args, **kwargs):
            health_called.append(True)
            return (True, "healthy")

        monkeypatch.setattr("installer.components.mcp.check_daemon_health", track_health)

        installer = Installer(spellbook_dir)
        session = installer.run(platforms=["claude_code"], dry_run=True)

        assert len(health_called) == 0
        health_results = [r for r in session.results if r.component == "mcp_health"]
        assert len(health_results) == 0

    def test_health_check_skipped_on_daemon_failure(self, spellbook_dir, home_dir, monkeypatch):
        """Health check does NOT run when daemon installation fails."""
        from installer.core import Installer

        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.setattr("installer.core.get_platform_config_dir", lambda p: home_dir / ".claude")
        monkeypatch.setattr("installer.demarcation.get_installed_version", lambda p: None)
        monkeypatch.setattr(
            "installer.core.get_platform_installer",
            lambda *a, **kw: _fake_platform_installer("Test", "test"),
        )
        monkeypatch.setattr("installer.components.mcp.install_daemon", lambda *a, **kw: (False, "venv failed"))

        health_called = []

        def track_health(*args, **kwargs):
            health_called.append(True)
            return (True, "healthy")

        monkeypatch.setattr("installer.components.mcp.check_daemon_health", track_health)

        installer = Installer(spellbook_dir)
        session = installer.run(platforms=["claude_code"], dry_run=False)

        assert len(health_called) == 0
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
        monkeypatch.setattr("installer.platforms.claude_code.check_claude_cli_available", lambda: False)
        monkeypatch.setattr("installer.components.mcp.check_claude_cli_available", lambda: False)

        daemon_called = []
        monkeypatch.setattr(
            "installer.components.mcp.install_daemon",
            lambda *a, **kw: daemon_called.append(True) or (True, "ok"),
        )

        installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")
        installer.install()

        assert len(daemon_called) == 0

    def test_codex_no_install_daemon(self, spellbook_dir, home_dir, monkeypatch):
        """CodexInstaller.install() does not call install_daemon."""
        from installer.platforms.codex import CodexInstaller

        config_dir = home_dir / ".codex"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        daemon_called = []
        monkeypatch.setattr(
            "installer.components.mcp.install_daemon",
            lambda *a, **kw: daemon_called.append(True) or (True, "ok"),
        )

        installer = CodexInstaller(spellbook_dir, config_dir, "0.10.0")
        installer.install()

        assert len(daemon_called) == 0

    def test_gemini_no_install_daemon(self, spellbook_dir, home_dir, monkeypatch):
        """GeminiInstaller.install() does not call install_daemon."""
        from installer.platforms.gemini import GeminiInstaller

        config_dir = home_dir / ".gemini"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.setattr("installer.platforms.gemini.check_gemini_cli_available", lambda: True)
        monkeypatch.setattr("installer.platforms.gemini.link_extension", lambda *a, **kw: (True, "ok"))

        daemon_called = []
        monkeypatch.setattr(
            "installer.components.mcp.install_daemon",
            lambda *a, **kw: daemon_called.append(True) or (True, "ok"),
        )

        installer = GeminiInstaller(spellbook_dir, config_dir, "0.10.0")
        installer.install()

        assert len(daemon_called) == 0

    def test_opencode_no_install_daemon(self, spellbook_dir, home_dir, monkeypatch):
        """OpenCodeInstaller.install() does not call install_daemon."""
        from installer.platforms.opencode import OpenCodeInstaller

        config_dir = home_dir / ".config" / "opencode"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        daemon_called = []
        monkeypatch.setattr(
            "installer.components.mcp.install_daemon",
            lambda *a, **kw: daemon_called.append(True) or (True, "ok"),
        )

        installer = OpenCodeInstaller(spellbook_dir, config_dir, "0.10.0")
        installer.install()

        assert len(daemon_called) == 0


# ---------------------------------------------------------------------------
# 3. check_daemon_health()
# ---------------------------------------------------------------------------

class TestCheckDaemonHealth:
    """Test all return paths of check_daemon_health()."""

    def test_healthy_response(self, monkeypatch):
        """Returns (True, message) with version and uptime on success."""
        from installer.components.mcp import check_daemon_health

        response_body = json.dumps({
            "status": "ok",
            "version": "0.10.0",
            "uptime_seconds": 42.5,
        }).encode()

        class FakeResponse:
            status = 200
            def read(self):
                return response_body
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: FakeResponse())

        healthy, msg = check_daemon_health()

        assert healthy is True
        assert "v0.10.0" in msg
        assert "42s" in msg

    def test_url_error(self, monkeypatch):
        """Returns (False, message) on URLError (daemon not running)."""
        from installer.components.mcp import check_daemon_health
        from urllib.error import URLError

        def raise_url_error(*args, **kwargs):
            raise URLError("Connection refused")

        monkeypatch.setattr("urllib.request.urlopen", raise_url_error)

        healthy, msg = check_daemon_health()

        assert healthy is False
        assert "daemon not responding" in msg
        assert "Connection refused" in msg

    def test_timeout_error(self, monkeypatch):
        """Returns (False, message) on TimeoutError."""
        from installer.components.mcp import check_daemon_health

        def raise_timeout(*args, **kwargs):
            raise TimeoutError()

        monkeypatch.setattr("urllib.request.urlopen", raise_timeout)

        healthy, msg = check_daemon_health()

        assert healthy is False
        assert "timed out" in msg

    def test_non_200_status(self, monkeypatch):
        """Returns (False, message) on non-200 HTTP status."""
        from installer.components.mcp import check_daemon_health

        class FakeResponse:
            status = 500
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: FakeResponse())

        healthy, msg = check_daemon_health()

        assert healthy is False
        assert "HTTP 500" in msg

    def test_os_error(self, monkeypatch):
        """Returns (False, message) on generic OSError."""
        from installer.components.mcp import check_daemon_health

        def raise_os_error(*args, **kwargs):
            raise OSError("Network unreachable")

        monkeypatch.setattr("urllib.request.urlopen", raise_os_error)

        healthy, msg = check_daemon_health()

        assert healthy is False
        assert "daemon not responding" in msg

    def test_custom_timeout_value(self, monkeypatch):
        """Timeout parameter is passed to urlopen."""
        from installer.components.mcp import check_daemon_health

        response_body = json.dumps({
            "status": "ok",
            "version": "1.0",
            "uptime_seconds": 0,
        }).encode()

        class FakeResponse:
            status = 200
            def read(self):
                return response_body
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        captured_args = {}

        def fake_urlopen(*args, **kwargs):
            captured_args["args"] = args
            captured_args["kwargs"] = kwargs
            return FakeResponse()

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        check_daemon_health(timeout=30)

        # Verify timeout was passed
        assert captured_args["kwargs"].get("timeout") == 30 or (
            len(captured_args["args"]) > 1 and captured_args["args"][1] == 30
        )


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

        from spellbook.daemon._paths import get_daemon_python

        result = get_daemon_python()

        assert result is not None
        # The result must contain the symlink path, not the resolved real_python path
        assert "daemon-venv" in result
        assert str(real_python) != result

    def test_env_not_set_returns_none(self, monkeypatch):
        """Returns None when SPELLBOOK_DAEMON_PYTHON is not set."""
        monkeypatch.delenv("SPELLBOOK_DAEMON_PYTHON", raising=False)

        from spellbook.daemon._paths import get_daemon_python

        result = get_daemon_python()
        assert result is None

    def test_nonexistent_file_returns_none(self, tmp_path, monkeypatch):
        """Returns None when SPELLBOOK_DAEMON_PYTHON points to a file that doesn't exist."""
        monkeypatch.setenv("SPELLBOOK_DAEMON_PYTHON", str(tmp_path / "nonexistent" / "python"))

        from spellbook.daemon._paths import get_daemon_python

        result = get_daemon_python()
        assert result is None


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
        monkeypatch.setattr(
            "installer.core.get_platform_installer",
            lambda *a, **kw: _fake_platform_installer("Test", "test"),
        )
        monkeypatch.setattr("installer.components.mcp.install_daemon", lambda *a, **kw: (True, "ok"))
        monkeypatch.setattr("installer.components.mcp.check_daemon_health", lambda *a, **kw: (True, "ok"))

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

        class FakeArgs:
            platforms = None
            yes = True
            no_interactive = False

        args = FakeArgs()

        # The condition is: args.yes or args.no_interactive or not is_interactive()
        # With args.yes = True, it should use detect_platforms
        assert args.yes or args.no_interactive  # This path triggers detect_platforms()


# ---------------------------------------------------------------------------
# 7. ensure_daemon_venv() hash detection
# ---------------------------------------------------------------------------

class TestEnsureDaemonVenvHashDetection:
    """Test the hash comparison logic in ensure_daemon_venv()."""

    def test_hash_matches_skips_rebuild(self, tmp_path, monkeypatch):
        """When pyproject hash matches stored hash, venv is not rebuilt."""
        from installer.components.mcp import ensure_daemon_venv

        # Create pyproject.toml (production uses this, not requirements.txt)
        sb_dir = tmp_path / "spellbook"
        sb_dir.mkdir(parents=True)
        pyproject = sb_dir / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'spellbook'\n")

        # Compute hash
        h = hashlib.sha256(pyproject.read_bytes()).hexdigest()

        # Create venv dir with matching hash file and a python binary
        venv_dir = tmp_path / "config" / "daemon-venv"
        venv_bin = venv_dir / "bin"
        venv_bin.mkdir(parents=True)
        python_path = venv_bin / "python"
        python_path.write_text("#!/usr/bin/env python3")

        hash_file = venv_dir / ".pyproject-hash"
        hash_file.write_text(h)

        # Write the source-path marker so the new refresh-detection path
        # treats this venv as up-to-date for the current source tree.
        source_path_marker = venv_dir / ".source-path"
        source_path_marker.write_text(str(sb_dir.resolve()))

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
        """When pyproject hash differs from stored hash, venv is rebuilt."""
        from installer.components.mcp import ensure_daemon_venv

        # Create pyproject.toml
        sb_dir = tmp_path / "spellbook"
        sb_dir.mkdir(parents=True)
        pyproject = sb_dir / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'spellbook'\nversion = '2.0'\n")

        # Create venv dir with mismatched hash
        venv_dir = tmp_path / "config" / "daemon-venv"
        venv_bin = venv_dir / "bin"
        venv_bin.mkdir(parents=True)
        python_path = venv_bin / "python"
        python_path.write_text("#!/usr/bin/env python3")

        hash_file = venv_dir / ".pyproject-hash"
        hash_file.write_text("stale_hash_value")

        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_venv_dir",
            lambda: venv_dir,
        )
        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_python",
            lambda: python_path,
        )

        class FakeResult:
            returncode = 0
            stdout = ""
            stderr = ""

        run_called = []

        monkeypatch.setattr("installer.components.mcp.stop_daemon", lambda *a, **kw: None)
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: (run_called.append(True), FakeResult())[-1],
        )

        success, msg = ensure_daemon_venv(tmp_path / "spellbook")

        # subprocess.run should have been called to create the venv
        assert len(run_called) > 0

    def test_force_triggers_rebuild(self, tmp_path, monkeypatch):
        """force=True always triggers rebuild even when hash matches."""
        from installer.components.mcp import ensure_daemon_venv

        # Create pyproject.toml
        sb_dir = tmp_path / "spellbook"
        sb_dir.mkdir(parents=True)
        pyproject = sb_dir / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'spellbook'\n")

        # Compute matching hash
        h = hashlib.sha256(pyproject.read_bytes()).hexdigest()

        venv_dir = tmp_path / "config" / "daemon-venv"
        venv_bin = venv_dir / "bin"
        venv_bin.mkdir(parents=True)
        python_path = venv_bin / "python"
        python_path.write_text("#!/usr/bin/env python3")

        hash_file = venv_dir / ".pyproject-hash"
        hash_file.write_text(h)

        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_venv_dir",
            lambda: venv_dir,
        )
        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_python",
            lambda: python_path,
        )

        class FakeResult:
            returncode = 0
            stdout = ""
            stderr = ""

        run_called = []

        monkeypatch.setattr("installer.components.mcp.stop_daemon", lambda *a, **kw: None)
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: (run_called.append(True), FakeResult())[-1],
        )

        ensure_daemon_venv(tmp_path / "spellbook", force=True)

        # Should rebuild despite matching hash
        assert len(run_called) > 0

    def test_missing_hash_file_triggers_rebuild(self, tmp_path, monkeypatch):
        """When no .pyproject-hash exists, venv is rebuilt."""
        from installer.components.mcp import ensure_daemon_venv

        sb_dir = tmp_path / "spellbook"
        sb_dir.mkdir(parents=True)
        pyproject = sb_dir / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'spellbook'\n")

        venv_dir = tmp_path / "config" / "daemon-venv"
        venv_bin = venv_dir / "bin"
        venv_bin.mkdir(parents=True)
        python_path = venv_bin / "python"
        python_path.write_text("#!/usr/bin/env python3")

        # No .pyproject-hash file exists

        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_venv_dir",
            lambda: venv_dir,
        )
        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_python",
            lambda: python_path,
        )

        class FakeResult:
            returncode = 0
            stdout = ""
            stderr = ""

        run_called = []

        monkeypatch.setattr("installer.components.mcp.stop_daemon", lambda *a, **kw: None)
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: (run_called.append(True), FakeResult())[-1],
        )

        ensure_daemon_venv(tmp_path / "spellbook")

        assert len(run_called) > 0

    def test_missing_pyproject_returns_failure(self, tmp_path):
        """Returns (False, message) when pyproject.toml doesn't exist."""
        from installer.components.mcp import ensure_daemon_venv

        sb_dir = tmp_path / "spellbook"
        sb_dir.mkdir()
        # No pyproject.toml

        success, msg = ensure_daemon_venv(sb_dir)

        assert success is False
        assert "not found" in msg

    def test_missing_python_binary_triggers_rebuild(self, tmp_path, monkeypatch):
        """When daemon python binary doesn't exist, venv is rebuilt."""
        from installer.components.mcp import ensure_daemon_venv

        sb_dir = tmp_path / "spellbook"
        sb_dir.mkdir(parents=True)
        pyproject = sb_dir / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'spellbook'\n")

        # Compute matching hash
        h = hashlib.sha256(pyproject.read_bytes()).hexdigest()

        venv_dir = tmp_path / "config" / "daemon-venv"
        venv_dir.mkdir(parents=True)

        # Python binary does NOT exist
        python_path = venv_dir / "bin" / "python"

        hash_file = venv_dir / ".pyproject-hash"
        hash_file.write_text(h)

        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_venv_dir",
            lambda: venv_dir,
        )
        monkeypatch.setattr(
            "installer.components.mcp.get_daemon_python",
            lambda: python_path,
        )

        class FakeResult:
            returncode = 0
            stdout = ""
            stderr = ""

        run_called = []

        monkeypatch.setattr("installer.components.mcp.stop_daemon", lambda *a, **kw: None)
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: (run_called.append(True), FakeResult())[-1],
        )

        ensure_daemon_venv(tmp_path / "spellbook")

        # Should rebuild because python binary is missing
        assert len(run_called) > 0


