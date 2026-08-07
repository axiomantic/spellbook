"""Tests for spellbook update command."""

import argparse
import json

import pytest
import tripwire

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

    def test_check_runs_without_crashing(self, capsys):
        """--check should run without errors."""

        find_repo_dir_mock = tripwire.mock("spellbook.cli.commands.update:_find_repo_dir")
        find_repo_dir_mock.calls(lambda: None)

        with tripwire:
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

        find_repo_dir_mock.assert_call(args=(), kwargs={})

    def test_check_json_output(self, capsys):
        """--check --json should produce valid JSON."""

        find_repo_dir_mock = tripwire.mock("spellbook.cli.commands.update:_find_repo_dir")
        find_repo_dir_mock.calls(lambda: "/fake/path")
        get_current_version_mock = tripwire.mock("spellbook.cli.commands.update:_get_current_version")
        get_current_version_mock.calls(lambda _dir: "0.30.0")
        get_latest_version_mock = tripwire.mock("spellbook.cli.commands.update:_get_latest_version")
        get_latest_version_mock.calls(lambda _dir: "0.32.0")

        with tripwire:
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

        find_repo_dir_mock.assert_call(args=(), kwargs={})
        get_current_version_mock.assert_call(args=("/fake/path",), kwargs={})
        get_latest_version_mock.assert_call(args=("/fake/path",), kwargs={})
