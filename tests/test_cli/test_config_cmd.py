"""Tests for spellbook.cli.commands.config - config get/set command."""

import argparse
import json

import pytest

from spellbook.cli.commands.config import register, run


class TestRegister:
    """Tests for register()."""

    def test_registers_config_subcommand(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        # Verify the subcommand parses without error
        args = parser.parse_args(["config", "get"])
        assert hasattr(args, "func")

    def test_config_help_exits_zero(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["config", "--help"])
        assert exc_info.value.code == 0

    def test_config_get_subcommand(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["config", "get"])
        assert hasattr(args, "func")

    def test_config_set_subcommand(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["config", "set", "mykey", "myval"])
        assert hasattr(args, "func")
        assert args.key == "mykey"
        assert args.value == "myval"

    def test_config_get_with_key(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["config", "get", "session_mode"])
        assert args.key == "session_mode"

    def test_config_get_without_key(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["config", "get"])
        assert args.key is None


class TestRun:
    """Tests for config get/set with a temp config file."""

    def test_config_set_then_get(self, tmp_path, monkeypatch, capsys):
        """Set a value, then get it back."""
        config_file = tmp_path / "spellbook.json"
        config_file.write_text("{}")

        monkeypatch.setattr(
            "spellbook.cli.commands.config.get_config_path",
            lambda: config_file,
        )
        # Also patch the config module's get_config_path for config_set/config_get
        monkeypatch.setattr(
            "spellbook.core.config.get_config_path",
            lambda: config_file,
        )

        # Set a value
        parser = argparse.ArgumentParser()
        parser.add_argument("--json", action="store_true", default=False)
        subparsers = parser.add_subparsers()
        register(subparsers)

        set_args = parser.parse_args(["config", "set", "test_key", "test_value"])
        set_args.func(set_args)

        captured = capsys.readouterr()
        assert "test_key" in captured.out

        # Get it back
        get_args = parser.parse_args(["config", "get", "test_key"])
        get_args.func(get_args)

        captured = capsys.readouterr()
        assert "test_value" in captured.out

    def test_config_get_all_json(self, tmp_path, monkeypatch, capsys):
        """Get all config values in JSON mode."""
        config_file = tmp_path / "spellbook.json"
        config_file.write_text('{"a": 1, "b": "two"}')

        monkeypatch.setattr(
            "spellbook.cli.commands.config.get_config_path",
            lambda: config_file,
        )

        parser = argparse.ArgumentParser()
        parser.add_argument("--json", action="store_true", default=False)
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["--json", "config", "get"])
        args.func(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["a"] == 1
        assert data["b"] == "two"

    def test_config_get_missing_key(self, tmp_path, monkeypatch, capsys):
        """Getting a nonexistent key prints nothing or null."""
        config_file = tmp_path / "spellbook.json"
        config_file.write_text("{}")

        monkeypatch.setattr(
            "spellbook.cli.commands.config.get_config_path",
            lambda: config_file,
        )

        parser = argparse.ArgumentParser()
        parser.add_argument("--json", action="store_true", default=False)
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["--json", "config", "get", "nonexistent"])
        args.func(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == {"nonexistent": None}

    def test_config_get_no_config_file(self, tmp_path, monkeypatch, capsys):
        """Get all when config file doesn't exist returns empty."""
        config_file = tmp_path / "nonexistent" / "spellbook.json"

        monkeypatch.setattr(
            "spellbook.cli.commands.config.get_config_path",
            lambda: config_file,
        )

        parser = argparse.ArgumentParser()
        parser.add_argument("--json", action="store_true", default=False)
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["--json", "config", "get"])
        args.func(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == {}
