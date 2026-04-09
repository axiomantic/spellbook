"""Tests for ServiceConfig dataclass, factory functions, and ServiceManager."""

import sys
from pathlib import Path
from xml.etree import ElementTree

import bigfoot
import pytest

from installer.compat import (
    Platform,
    ServiceConfig,
    ServiceManager,
    mcp_service_config,
    tts_service_config,
)
from spellbook.core.paths import get_data_dir, get_log_dir


class TestServiceConfig:
    def test_service_config_all_fields(self):
        config = ServiceConfig(
            launchd_label="com.test.svc",
            service_name="test-svc",
            schtasks_name="TestSvc",
            description="Test Service",
            executable=Path("/usr/bin/python"),
            args=["-m", "test"],
            working_directory=Path("/tmp"),
            environment={"PATH": "/usr/bin"},
            log_stdout=Path("/tmp/test.log"),
            log_stderr=Path("/tmp/test.err.log"),
        )
        assert config == ServiceConfig(
            launchd_label="com.test.svc",
            service_name="test-svc",
            schtasks_name="TestSvc",
            description="Test Service",
            executable=Path("/usr/bin/python"),
            args=["-m", "test"],
            working_directory=Path("/tmp"),
            environment={"PATH": "/usr/bin"},
            log_stdout=Path("/tmp/test.log"),
            log_stderr=Path("/tmp/test.err.log"),
            pid_file=None,
            keep_alive=True,
            health_check_port=None,
            health_check_host="127.0.0.1",
        )

    def test_service_config_optional_fields(self):
        config = ServiceConfig(
            launchd_label="com.test.svc",
            service_name="test-svc",
            schtasks_name="TestSvc",
            description="Test Service",
            executable=Path("/usr/bin/python"),
            args=["-m", "test"],
            working_directory=Path("/tmp"),
            environment={},
            log_stdout=Path("/tmp/test.log"),
            log_stderr=Path("/tmp/test.err.log"),
            pid_file=Path("/tmp/test.pid"),
            keep_alive=False,
            health_check_port=9090,
            health_check_host="0.0.0.0",
        )
        assert config == ServiceConfig(
            launchd_label="com.test.svc",
            service_name="test-svc",
            schtasks_name="TestSvc",
            description="Test Service",
            executable=Path("/usr/bin/python"),
            args=["-m", "test"],
            working_directory=Path("/tmp"),
            environment={},
            log_stdout=Path("/tmp/test.log"),
            log_stderr=Path("/tmp/test.err.log"),
            pid_file=Path("/tmp/test.pid"),
            keep_alive=False,
            health_check_port=9090,
            health_check_host="0.0.0.0",
        )


class TestMcpServiceConfig:
    def test_returns_service_config_with_daemon_python(self, tmp_path, monkeypatch):
        # Create a fake daemon python so Path.exists() returns True
        fake_python = tmp_path / "bin" / "python"
        fake_python.parent.mkdir(parents=True)
        fake_python.write_text("#!/usr/bin/env python")

        mock_get_daemon_python = bigfoot.mock(
            "installer.compat:_get_daemon_python_for_config"
        )
        mock_get_daemon_python.returns(str(fake_python))
        mock_get_daemon_path = bigfoot.mock(
            "installer.compat:_get_daemon_path"
        )
        mock_get_daemon_path.returns("/usr/local/bin:/usr/bin")
        monkeypatch.setenv("SPELLBOOK_CONFIG_DIR", str(tmp_path / "config"))

        with bigfoot:
            config = mcp_service_config(
                spellbook_dir=Path("/opt/spellbook"),
                port=8765,
                host="127.0.0.1",
            )

        spellbook_dir = Path("/opt/spellbook")
        assert config == ServiceConfig(
            launchd_label="com.spellbook.mcp",
            service_name="spellbook-mcp",
            schtasks_name="SpellbookMCP",
            description="Spellbook MCP Server",
            executable=fake_python,
            args=["-m", "spellbook.mcp"],
            working_directory=spellbook_dir,
            environment={
                "PATH": "/usr/local/bin:/usr/bin",
                "SPELLBOOK_MCP_TRANSPORT": "streamable-http",
                "SPELLBOOK_MCP_HOST": "127.0.0.1",
                "SPELLBOOK_MCP_PORT": "8765",
                "SPELLBOOK_DIR": str(spellbook_dir),
            },
            log_stdout=get_log_dir() / "mcp.log",
            log_stderr=get_log_dir() / "mcp.err.log",
            pid_file=tmp_path / "config" / "spellbook-mcp.pid",
            keep_alive=True,
            health_check_port=8765,
            health_check_host="127.0.0.1",
        )

        with bigfoot.in_any_order():
            mock_get_daemon_python.assert_call(args=(), kwargs={})
            mock_get_daemon_path.assert_call(args=(), kwargs={})

    def test_falls_back_to_uv_when_no_daemon_python(self, tmp_path, monkeypatch):
        mock_get_daemon_python = bigfoot.mock(
            "installer.compat:_get_daemon_python_for_config"
        )
        mock_get_daemon_python.returns(None)
        mock_get_daemon_path = bigfoot.mock(
            "installer.compat:_get_daemon_path"
        )
        mock_get_daemon_path.returns("/usr/bin")
        mock_which = bigfoot.mock("installer.compat:shutil.which")
        mock_which.returns("/usr/local/bin/uv")
        monkeypatch.setenv("SPELLBOOK_CONFIG_DIR", str(tmp_path / "config"))

        with bigfoot:
            config = mcp_service_config(
                spellbook_dir=Path("/opt/spellbook"),
                port=8765,
                host="127.0.0.1",
            )

        assert config.executable == Path("/usr/local/bin/uv")
        assert config.args == ["run", "python", "-m", "spellbook.mcp"]

        with bigfoot.in_any_order():
            mock_get_daemon_python.assert_call(args=(), kwargs={})
            mock_get_daemon_path.assert_call(args=(), kwargs={})
            mock_which.assert_call(args=("uv",), kwargs={})


class TestTtsServiceConfig:
    def test_returns_service_config_defaults(self):
        tts_venv = Path("/home/user/.local/spellbook/tts-venv")
        config = tts_service_config(tts_venv_dir=tts_venv)

        assert isinstance(config, ServiceConfig)
        assert config.launchd_label == "com.spellbook.tts"
        assert config.service_name == "spellbook-tts"
        assert config.schtasks_name == "SpellbookTTS"
        assert config.description == "Spellbook TTS Server"
        if sys.platform == "win32":
            assert config.executable == tts_venv / "Scripts" / "python.exe"
        else:
            assert config.executable == tts_venv / "bin" / "python"
        assert config.working_directory == get_data_dir()
        assert config.environment == {}
        assert config.pid_file is None
        assert config.keep_alive is True
        assert config.health_check_port == 10200
        assert config.health_check_host == "127.0.0.1"

    def test_default_args_include_port_and_voice(self):
        tts_venv = Path("/home/user/.local/spellbook/tts-venv")
        config = tts_service_config(tts_venv_dir=tts_venv)

        assert config.args == [
            "-m", "wyoming_kokoro_torch",
            "--uri", "tcp://127.0.0.1:10200",
            "--device", "cpu",
            "--voice", "af_heart",
            "--data-dir", str(get_data_dir() / "tts-data"),
        ]

    def test_custom_port_device_voice(self):
        tts_venv = Path("/home/user/.local/spellbook/tts-venv")
        config = tts_service_config(
            tts_venv_dir=tts_venv,
            port=10300,
            device="cuda",
            voice="af_bella",
        )

        assert config.args == [
            "-m", "wyoming_kokoro_torch",
            "--uri", "tcp://127.0.0.1:10300",
            "--device", "cuda",
            "--voice", "af_bella",
            "--data-dir", str(get_data_dir() / "tts-data"),
        ]
        assert config.health_check_port == 10300

    def test_custom_data_dir(self):
        tts_venv = Path("/home/user/.local/spellbook/tts-venv")
        config = tts_service_config(
            tts_venv_dir=tts_venv,
            data_dir=Path("/custom/data"),
        )

        assert config.args == [
            "-m", "wyoming_kokoro_torch",
            "--uri", "tcp://127.0.0.1:10200",
            "--device", "cpu",
            "--voice", "af_heart",
            "--data-dir", "/custom/data",
        ]

    def test_log_paths(self):
        tts_venv = Path("/home/user/.local/spellbook/tts-venv")
        config = tts_service_config(tts_venv_dir=tts_venv)

        assert config.log_stdout == get_log_dir() / "tts.log"
        assert config.log_stderr == get_log_dir() / "tts.err.log"


# ---------------------------------------------------------------------------
# Task 2: ServiceManager with ServiceConfig
# ---------------------------------------------------------------------------


def _make_config(**overrides) -> ServiceConfig:
    """Build a ServiceConfig with sensible test defaults."""
    defaults = dict(
        launchd_label="com.test.svc",
        service_name="test-svc",
        schtasks_name="TestSvc",
        description="Test Service",
        executable=Path("/usr/bin/python"),
        args=["-m", "test"],
        working_directory=Path("/tmp"),
        environment={"KEY": "val"},
        log_stdout=Path("/tmp/test.log"),
        log_stderr=Path("/tmp/test.err.log"),
    )
    defaults.update(overrides)
    return ServiceConfig(**defaults)


class TestServiceManagerAcceptsConfig:
    """ServiceManager.__init__ accepts a ServiceConfig."""

    def test_accepts_service_config(self):
        config = _make_config()
        manager = ServiceManager(config)
        assert manager.config is config

    def test_plist_path_uses_config_label(self):
        config = _make_config(launchd_label="com.custom.label")
        manager = ServiceManager(config)
        path = manager._launchd_plist_path()
        assert path == (
            Path.home() / "Library" / "LaunchAgents" / "com.custom.label.plist"
        )

    def test_systemd_path_uses_config_name(self):
        config = _make_config(service_name="custom-svc")
        manager = ServiceManager(config)
        path = manager._systemd_service_path()
        assert path == (
            Path.home() / ".config" / "systemd" / "user" / "custom-svc.service"
        )

    def test_is_installed_macos_plist_exists(self, tmp_path, monkeypatch):
        import spellbook.core.services as services_mod

        monkeypatch.setattr(services_mod, "get_platform", lambda: Platform.MACOS)

        plist = tmp_path / "com.test.svc.plist"
        plist.write_text("<plist/>")
        config = _make_config(launchd_label="com.test.svc")
        manager = ServiceManager(config)

        mock_plist = bigfoot.mock.object(manager, "_launchd_plist_path")
        mock_plist.returns(plist)

        with bigfoot:
            result = manager.is_installed()

        assert result is True
        mock_plist.assert_call(args=(), kwargs={})

    def test_is_installed_macos_plist_missing(self, tmp_path, monkeypatch):
        import spellbook.core.services as services_mod

        monkeypatch.setattr(services_mod, "get_platform", lambda: Platform.MACOS)

        config = _make_config()
        manager = ServiceManager(config)

        mock_plist = bigfoot.mock.object(manager, "_launchd_plist_path")
        mock_plist.returns(tmp_path / "nonexistent.plist")

        with bigfoot:
            result = manager.is_installed()

        assert result is False
        mock_plist.assert_call(args=(), kwargs={})

    def test_is_installed_linux_service_exists(self, tmp_path, monkeypatch):
        import spellbook.core.services as services_mod

        monkeypatch.setattr(services_mod, "get_platform", lambda: Platform.LINUX)

        service_file = tmp_path / "test-svc.service"
        service_file.write_text("[Unit]")
        config = _make_config(service_name="test-svc")
        manager = ServiceManager(config)

        mock_svc = bigfoot.mock.object(manager, "_systemd_service_path")
        mock_svc.returns(service_file)

        with bigfoot:
            result = manager.is_installed()

        assert result is True
        mock_svc.assert_call(args=(), kwargs={})


class TestServiceManagerIsRunning:
    """is_running() uses TCP probe when health_check_port is set."""

    def test_is_running_with_health_check_port_false(self):
        """Non-routable IP should fail TCP probe quickly."""
        config = _make_config(health_check_port=9, health_check_host="192.0.2.1")
        manager = ServiceManager(config)
        assert manager.is_running() is False

    @pytest.mark.allow("subprocess")
    def test_is_running_without_health_check_port_falls_back_to_platform(
        self, monkeypatch
    ):
        """When health_check_port is None, falls back to platform checks."""
        import spellbook.core.services as services_mod

        monkeypatch.setattr(services_mod, "get_platform", lambda: Platform.MACOS)

        config = _make_config(health_check_port=None)
        manager = ServiceManager(config)

        bigfoot.subprocess_mock.mock_run(
            command=["launchctl", "list", "com.test.svc"],
            returncode=1,
        )

        with bigfoot:
            result = manager.is_running()

        assert result is False
        bigfoot.subprocess_mock.assert_run(
            command=["launchctl", "list", "com.test.svc"],
            returncode=1,
            stdout="",
            stderr="",
        )


class TestServiceManagerGenerateTaskXml:
    """_generate_task_xml() uses config fields."""

    def test_xml_contains_config_executable_and_args(self):
        executable = Path("/usr/bin/python3")
        working_dir = Path("/opt/myapp")
        config = _make_config(
            executable=executable,
            args=["-m", "myservice", "--port", "8080"],
            working_directory=working_dir,
        )
        manager = ServiceManager(config)
        xml = manager._generate_task_xml()

        root = ElementTree.fromstring(xml)
        ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}

        # Command wraps in cmd.exe for stdout/stderr redirection
        command = root.find(".//t:Exec/t:Command", ns)
        assert command is not None
        assert command.text == "cmd.exe"

        # Arguments contain the original command with log redirection
        arguments = root.find(".//t:Exec/t:Arguments", ns)
        assert arguments is not None
        assert str(executable) in arguments.text
        assert "-m myservice --port 8080" in arguments.text
        assert str(config.log_stdout) in arguments.text
        assert str(config.log_stderr) in arguments.text

        workdir = root.find(".//t:Exec/t:WorkingDirectory", ns)
        assert workdir is not None
        assert workdir.text == str(working_dir)


class TestServiceManagerStop:
    """stop() uses config.pid_file and config.service_name."""

    def test_stop_uses_config_pid_file(self, tmp_path, monkeypatch):
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("12345")
        config = _make_config(pid_file=pid_file)
        manager = ServiceManager(config)

        # Mock _pid_exists to return True so the PID-based kill path is taken
        mock_pid_exists = bigfoot.mock("spellbook.core.services:_pid_exists")
        mock_pid_exists.returns(True)

        # Mock _kill_process to verify os.kill is attempted with the correct PID
        mock_kill = bigfoot.mock.object(manager, "_kill_process")
        mock_kill.returns(None)

        with bigfoot:
            success, msg = manager.stop()

        assert success is True
        assert "12345" in msg
        mock_pid_exists.assert_call(args=(12345,), kwargs={})
        mock_kill.assert_call(args=(12345,), kwargs={})

    @pytest.mark.allow("subprocess")
    def test_stop_without_pid_file_uses_platform(self, tmp_path, monkeypatch):
        import spellbook.core.services as services_mod

        monkeypatch.setattr(services_mod, "get_platform", lambda: Platform.LINUX)

        config = _make_config(pid_file=None, service_name="my-svc")
        manager = ServiceManager(config)

        bigfoot.subprocess_mock.mock_run(
            command=["systemctl", "--user", "stop", "my-svc"],
            returncode=0,
        )

        with bigfoot:
            success, msg = manager.stop()

        assert success is True
        bigfoot.subprocess_mock.assert_run(
            command=["systemctl", "--user", "stop", "my-svc"],
            returncode=0,
            stdout="",
            stderr="",
        )
