"""Tests for spellbook.cli.commands.session - session list/export command."""

import argparse
import json

import pytest

from spellbook.cli.commands.session import register


class TestRegister:
    """Tests for register()."""

    def test_registers_session_subcommand(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["session", "list"])
        assert hasattr(args, "func")

    def test_session_help_exits_zero(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["session", "--help"])
        assert exc_info.value.code == 0

    def test_list_subcommand_with_project(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["session", "list", "--project", "myproj"])
        assert args.project == "myproj"

    def test_export_subcommand(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["session", "export", "abc123", "--format", "json"])
        assert hasattr(args, "func")
        assert args.session_id == "abc123"
        assert args.format == "json"


class TestListRun:
    """Tests for session list."""

    def test_list_no_sessions_dir(self, tmp_path, monkeypatch, capsys):
        """List with no sessions directory returns empty."""
        monkeypatch.setattr(
            "spellbook.cli.commands.session._get_projects_dir",
            lambda: tmp_path / "nonexistent",
        )

        parser = argparse.ArgumentParser()
        parser.add_argument("--json", action="store_true", default=False)
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["--json", "session", "list"])
        args.func(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_with_sessions(self, tmp_path, monkeypatch, capsys):
        """List finds session files in project dirs."""
        # Create a fake project dir with a session file
        proj_dir = tmp_path / "-Users-test-project"
        proj_dir.mkdir(parents=True)
        session_file = proj_dir / "abc123.jsonl"
        session_file.write_text(
            '{"type": "user", "timestamp": "2025-01-01T00:00:00Z", '
            '"message": {"content": "hello"}}\n'
        )

        monkeypatch.setattr(
            "spellbook.cli.commands.session._get_projects_dir",
            lambda: tmp_path,
        )

        parser = argparse.ArgumentParser()
        parser.add_argument("--json", action="store_true", default=False)
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["--json", "session", "list"])
        args.func(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) >= 1


class TestExportRun:
    """Tests for session export."""

    def test_export_nonexistent_session(self, tmp_path, monkeypatch, capsys):
        """Export nonexistent session shows error."""
        monkeypatch.setattr(
            "spellbook.cli.commands.session._get_projects_dir",
            lambda: tmp_path,
        )

        parser = argparse.ArgumentParser()
        parser.add_argument("--json", action="store_true", default=False)
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["--json", "session", "export", "nonexistent"])
        args.func(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data.get("error") is not None
