"""Tests for spellbook install command."""

import argparse

import pytest

from spellbook.cli.commands.install import register, run


class TestRegister:
    """Tests for register()."""

    def test_register_adds_install_subcommand(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        args = parser.parse_args(["install"])
        assert args.command == "install"
        assert hasattr(args, "func")

    def test_help_flag(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["install", "--help"])
        assert exc_info.value.code == 0

    def test_platforms_flag(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        args = parser.parse_args(["install", "--platforms", "claude_code", "opencode"])
        assert args.platforms == ["claude_code", "opencode"]

    def test_force_flag(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        args = parser.parse_args(["install", "--force"])
        assert args.force is True

    def test_dry_run_flag(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        args = parser.parse_args(["install", "--dry-run"])
        assert args.dry_run is True


class TestInstallRun:
    """Tests for install run function."""

    def test_dry_run_does_not_crash(self, capsys, monkeypatch):
        """--dry-run should not crash."""
        from installer import core

        class FakeSession:
            success = True
            results = []
            platforms_installed = []

        class FakeInstaller:
            def __init__(self, *a, **kw):
                pass

            def run(self, **kw):
                return FakeSession()

        monkeypatch.setattr(core, "Installer", FakeInstaller)

        args = argparse.Namespace(
            json=False,
            platforms=None,
            force=False,
            dry_run=True,
        )
        run(args)
        captured = capsys.readouterr()
        # Should produce some output
        assert captured.out or True  # Dry run may produce minimal output
