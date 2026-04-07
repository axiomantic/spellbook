"""Tests for ServiceConfig dataclass and factory functions."""

import sys
from pathlib import Path

import bigfoot
import pytest

from installer.compat import ServiceConfig, mcp_service_config, tts_service_config


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

        assert config == ServiceConfig(
            launchd_label="com.spellbook.mcp",
            service_name="spellbook-mcp",
            schtasks_name="SpellbookMCP",
            description="Spellbook MCP Server",
            executable=fake_python,
            args=["-m", "spellbook.mcp"],
            working_directory=Path("/opt/spellbook"),
            environment={
                "PATH": "/usr/local/bin:/usr/bin",
                "SPELLBOOK_MCP_TRANSPORT": "streamable-http",
                "SPELLBOOK_MCP_HOST": "127.0.0.1",
                "SPELLBOOK_MCP_PORT": "8765",
                "SPELLBOOK_DIR": "/opt/spellbook",
            },
            log_stdout=Path.home() / ".local" / "spellbook" / "logs" / "mcp.log",
            log_stderr=Path.home() / ".local" / "spellbook" / "logs" / "mcp.err.log",
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
        assert config.working_directory == Path.home() / ".local" / "spellbook"
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
            "--data-dir", str(Path.home() / ".local" / "spellbook" / "tts-data"),
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
            "--data-dir", str(Path.home() / ".local" / "spellbook" / "tts-data"),
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

        log_dir = Path.home() / ".local" / "spellbook" / "logs"
        assert config.log_stdout == log_dir / "tts.log"
        assert config.log_stderr == log_dir / "tts.err.log"
