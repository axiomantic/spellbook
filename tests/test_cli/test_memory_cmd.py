"""Tests for spellbook.cli.commands.memory - memory search/export command.

All mocks use tripwire per project policy (see AGENTS.md, "Testing with
Tripwire"). ``monkeypatch.setattr`` of module attributes is forbidden.
"""

import argparse
import json

import pytest
import tripwire

from spellbook.cli.commands.memory import register


class TestRegister:
    """Tests for register()."""

    def test_registers_memory_subcommand(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["memory", "search", "test"])
        assert hasattr(args, "func")

    def test_memory_help_exits_zero(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["memory", "--help"])
        assert exc_info.value.code == 0

    def test_search_subcommand_args(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["memory", "search", "my query", "--limit", "5", "--namespace", "proj"])
        assert args.query == "my query"
        assert args.limit == 5
        assert args.namespace == "proj"

    def test_export_subcommand(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["memory", "export", "--format", "json"])
        assert hasattr(args, "func")
        assert args.format == "json"

    def test_search_default_limit(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["memory", "search", "test"])
        assert args.limit == 10

    def test_search_default_namespace(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["memory", "search", "test"])
        assert args.namespace == "default"


class TestSearchRun:
    """Tests for memory search with no DB."""

    def test_search_no_db_returns_empty(self, tmp_path, capsys):
        """Search with nonexistent DB returns empty gracefully."""
        db_path = tmp_path / "nonexistent.db"
        mock_get_db_path = tripwire.mock("spellbook.cli.commands.memory:get_db_path")
        mock_get_db_path.__call__.required(False).calls(lambda: db_path)

        parser = argparse.ArgumentParser()
        parser.add_argument("--json", action="store_true", default=False)
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["--json", "memory", "search", "test"])
        args.func(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["memories"] == []
        assert data["count"] == 0


class TestExportRun:
    """Tests for memory export with no DB."""

    def test_export_no_db_returns_empty(self, tmp_path, capsys):
        """Export with nonexistent DB returns empty gracefully."""
        db_path = tmp_path / "nonexistent.db"
        mock_get_db_path = tripwire.mock("spellbook.cli.commands.memory:get_db_path")
        mock_get_db_path.__call__.required(False).calls(lambda: db_path)

        parser = argparse.ArgumentParser()
        parser.add_argument("--json", action="store_true", default=False)
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["--json", "memory", "export"])
        args.func(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 0
