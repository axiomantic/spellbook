"""Tests for spellbook.cli.commands.security - security events command."""

import argparse
import json

import pytest

from spellbook.cli.commands.security import register


class TestRegister:
    """Tests for register()."""

    def test_registers_security_subcommand(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["security", "events"])
        assert hasattr(args, "func")

    def test_security_help_exits_zero(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["security", "--help"])
        assert exc_info.value.code == 0

    def test_events_subcommand_args(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args([
            "security", "events",
            "--severity", "HIGH",
            "--limit", "20",
        ])
        assert args.severity == "HIGH"
        assert args.limit == 20

    def test_events_follow_flag(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["security", "events", "--follow"])
        assert args.follow is True

    def test_events_default_limit(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["security", "events"])
        assert args.limit == 50


class TestEventsRun:
    """Tests for security events with no DB."""

    def test_events_no_db_returns_empty(self, tmp_path, monkeypatch, capsys):
        """Events query with no DB returns empty gracefully."""
        monkeypatch.setattr(
            "spellbook.cli.commands.security._get_db_path_str",
            lambda: str(tmp_path / "nonexistent.db"),
        )

        parser = argparse.ArgumentParser()
        parser.add_argument("--json", action="store_true", default=False)
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["--json", "security", "events"])
        args.func(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data.get("events"), list)
        assert data["count"] == 0

    def test_events_with_severity_filter(self, tmp_path, monkeypatch, capsys):
        """Events with severity filter returns empty gracefully."""
        monkeypatch.setattr(
            "spellbook.cli.commands.security._get_db_path_str",
            lambda: str(tmp_path / "nonexistent.db"),
        )

        parser = argparse.ArgumentParser()
        parser.add_argument("--json", action="store_true", default=False)
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["--json", "security", "events", "--severity", "CRITICAL"])
        args.func(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data.get("events"), list)
