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
        """Search with nonexistent DB returns empty gracefully.

        The SUT calls ``get_db_path()`` at most once via the registered
        tripwire mock. We pre-stack a single required(False) entry so
        the no-DB short-circuit (which may bypass get_db_path entirely
        depending on import-time caching) does not produce an
        UnusedMocksError if the call never fires. After ``with tripwire:``
        exits, ``in_any_order`` drains the recorded calls.
        """
        db_path = tmp_path / "nonexistent.db"
        mock_get_db_path = tripwire.mock("spellbook.cli.commands.memory:get_db_path")
        mock_get_db_path.__call__.required(False).calls(lambda: db_path)

        parser = argparse.ArgumentParser()
        parser.add_argument("--json", action="store_true", default=False)
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["--json", "memory", "search", "test"])

        with tripwire:
            args.func(args)

        # Drain the timeline -- the SUT may invoke get_db_path zero or
        # one time depending on the short-circuit path; in_any_order
        # tolerates both without weakening the test's content
        # assertions on captured stdout below.
        with tripwire.in_any_order():
            mock_get_db_path.__call__.required(False).assert_call()
            # do_memory_recall probes for the optional qmd + serena CLI
            # tools via shutil.which; both are intercepted by tripwire's
            # subprocess plugin and must be drained.
            tripwire.subprocess.assert_which(name="qmd", returns=None)
            tripwire.subprocess.assert_which(name="serena", returns=None)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["memories"] == []
        assert data["count"] == 0


class TestExportRun:
    """Tests for memory export with no DB."""

    def test_export_no_db_returns_empty(self, tmp_path, capsys):
        """Export with nonexistent DB returns empty gracefully.

        See ``test_search_no_db_returns_empty`` above for the rationale
        on the optional ``get_db_path`` invocation and the
        in_any_order drain pattern.
        """
        db_path = tmp_path / "nonexistent.db"
        mock_get_db_path = tripwire.mock("spellbook.cli.commands.memory:get_db_path")
        mock_get_db_path.__call__.required(False).calls(lambda: db_path)

        parser = argparse.ArgumentParser()
        parser.add_argument("--json", action="store_true", default=False)
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["--json", "memory", "export"])

        with tripwire:
            args.func(args)

        # Export takes the no-DB short-circuit before any subprocess
        # probes (no qmd/serena which() calls -- those are only emitted
        # by do_memory_recall on the search path). get_db_path is the
        # single intercepted call to drain.
        with tripwire.in_any_order():
            mock_get_db_path.__call__.required(False).assert_call()

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 0
