"""Tests for spellbook admin command."""

import argparse

import pytest

from spellbook.cli.commands.admin import register, run


class TestRegister:
    """Tests for register()."""

    def test_register_adds_admin_subcommand(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        args = parser.parse_args(["admin", "open"])
        assert args.command == "admin"
        assert hasattr(args, "func")

    def test_help_flag(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["admin", "--help"])
        assert exc_info.value.code == 0

    def test_open_subcommand(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        args = parser.parse_args(["admin", "open"])
        assert args.admin_command == "open"

    def test_open_port_flag(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        args = parser.parse_args(["admin", "open", "--port", "9000"])
        assert args.port == 9000


class TestAdminRun:
    """Tests for admin run function."""

    def test_handles_missing_token_gracefully(self, capsys, monkeypatch, tmp_path):
        """Should handle missing token without crashing."""
        from spellbook.admin import cli as admin_cli

        monkeypatch.setattr(admin_cli, "_find_mcp_token", lambda: None)

        args = argparse.Namespace(
            json=False,
            admin_command="open",
            port=None,
        )
        try:
            run(args)
        except SystemExit as exc:
            assert exc.code in (1, 2)  # Graceful error exit
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "token" in combined.lower() or "error" in combined.lower()

    def test_no_subcommand_shows_usage(self, capsys):
        """admin with no subcommand should show usage."""
        args = argparse.Namespace(
            json=False,
            admin_command=None,
        )
        with pytest.raises(SystemExit) as exc_info:
            run(args)
        assert exc_info.value.code == 2
