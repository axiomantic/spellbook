"""Tests for spellbook.cli.commands.memory - memory search/export command."""

import argparse
import json

import pytest

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

    def test_search_no_db_returns_empty(self, tmp_path, monkeypatch, capsys):
        """Search with nonexistent DB returns empty gracefully."""
        fake_db = str(tmp_path / "nonexistent.db")
        monkeypatch.setattr(
            "spellbook.cli.commands.memory.get_db_path",
            lambda: tmp_path / "nonexistent.db",
        )

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

    def test_export_no_db_returns_empty(self, tmp_path, monkeypatch, capsys):
        """Export with nonexistent DB returns empty gracefully."""
        monkeypatch.setattr(
            "spellbook.cli.commands.memory.get_db_path",
            lambda: tmp_path / "nonexistent.db",
        )

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
