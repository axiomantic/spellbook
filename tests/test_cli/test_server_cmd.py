"""Tests for spellbook server command."""

import argparse
import json

import pytest

from spellbook.cli.commands.server import register, run


class TestRegister:
    """Tests for register()."""

    def test_register_adds_server_subcommand(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        args = parser.parse_args(["server", "status"])
        assert args.command == "server"
        assert hasattr(args, "func")

    def test_help_flag(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["server", "--help"])
        assert exc_info.value.code == 0

    def test_subcommands_exist(self):
        """All expected subcommands should be available."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)

        for subcmd in ("start", "stop", "restart", "status", "install", "uninstall", "logs"):
            args = parser.parse_args(["server", subcmd])
            assert args.server_command == subcmd

    def test_start_foreground_flag(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        args = parser.parse_args(["server", "start", "--foreground"])
        assert args.foreground is True

    def test_logs_follow_flag(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        args = parser.parse_args(["server", "logs", "--follow"])
        assert args.follow is True

    def test_logs_lines_flag(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        args = parser.parse_args(["server", "logs", "-n", "100"])
        assert args.lines == 100


class TestServerStatus:
    """Tests for server status subcommand."""

    def test_status_runs_without_crashing(self, capsys, monkeypatch):
        """status should run without errors."""
        from spellbook.daemon import manager

        monkeypatch.setattr(manager, "daemon_status", lambda: {
            "running": False,
            "pid": None,
            "port": 8765,
            "uptime": None,
        })

        args = argparse.Namespace(
            json=False,
            command="server",
            server_command="status",
        )
        run(args)
        captured = capsys.readouterr()
        assert "running" in captured.out.lower() or "status" in captured.out.lower()

    def test_status_json_valid(self, capsys, monkeypatch):
        """status --json should produce valid JSON."""
        from spellbook.daemon import manager

        monkeypatch.setattr(manager, "daemon_status", lambda: {
            "running": False,
            "pid": None,
            "port": 8765,
            "uptime": None,
        })

        args = argparse.Namespace(
            json=True,
            command="server",
            server_command="status",
        )
        run(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "running" in data
