"""Tests for spellbook update command."""

import argparse
import json

import pytest

from spellbook.cli.commands.update import register, run


class TestRegister:
    """Tests for register()."""

    def test_register_adds_update_subcommand(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        args = parser.parse_args(["update"])
        assert args.command == "update"
        assert hasattr(args, "func")

    def test_help_flag(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["update", "--help"])
        assert exc_info.value.code == 0

    def test_check_flag(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        args = parser.parse_args(["update", "--check"])
        assert args.check is True


class TestUpdateRun:
    """Tests for update run function."""

    def test_check_runs_without_crashing(self, capsys, monkeypatch):
        """--check should run without errors."""
        import spellbook.cli.commands.update as update_mod

        monkeypatch.setattr(update_mod, "_find_repo_dir", lambda: None)

        args = argparse.Namespace(
            json=False,
            check=True,
        )
        # When repo dir is None, should report error and return
        try:
            run(args)
        except SystemExit:
            pass
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert combined  # Produces some output

    def test_check_json_output(self, capsys, monkeypatch):
        """--check --json should produce valid JSON."""
        import spellbook.cli.commands.update as update_mod

        monkeypatch.setattr(
            update_mod,
            "_find_repo_dir",
            lambda: "/fake/path",
        )
        monkeypatch.setattr(
            update_mod,
            "_get_current_version",
            lambda _dir: "0.30.0",
        )
        monkeypatch.setattr(
            update_mod,
            "_get_latest_version",
            lambda _dir: "0.32.0",
        )

        args = argparse.Namespace(
            json=True,
            check=True,
        )
        run(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "current_version" in data
        assert "latest_version" in data
        assert "update_available" in data
