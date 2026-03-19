"""Tests for spellbook.cli.main - CLI entry point."""

import subprocess
import sys
import tempfile

import pytest

from spellbook.cli.main import create_parser, main


class TestCreateParser:
    """Tests for create_parser()."""

    def test_parser_has_version_flag(self):
        parser = create_parser()
        # --version triggers SystemExit(0) in argparse
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0

    def test_parser_has_json_flag(self):
        parser = create_parser()
        args = parser.parse_args(["--json"])
        assert args.json is True

    def test_parser_json_default_false(self):
        parser = create_parser()
        args = parser.parse_args([])
        assert args.json is False


class TestMain:
    """Tests for main() entry point."""

    def test_help_flag_exits_zero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_version_flag_exits_zero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_version_output_contains_version_string(self, capsys):
        with pytest.raises(SystemExit):
            main(["--version"])
        captured = capsys.readouterr()
        # Should contain some version string (digits and dots)
        assert any(c.isdigit() for c in captured.out)

    def test_no_args_prints_help_exits_two(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 2

    def test_unknown_command_exits_two(self, capsys):
        """Unknown subcommand should print help and exit 2."""
        with pytest.raises(SystemExit) as exc_info:
            main(["nonexistent-command"])
        assert exc_info.value.code == 2

    def test_keyboard_interrupt_exits_130(self, monkeypatch):
        """KeyboardInterrupt during command execution should exit 130."""

        def fake_func(args):
            raise KeyboardInterrupt

        # Create a parser with a test subcommand that raises KeyboardInterrupt
        import spellbook.cli.main as cli_module

        original_create = cli_module.create_parser

        def patched_create_parser():
            parser = original_create()
            # Add a test subcommand
            subparsers_actions = [
                a for a in parser._subparsers._actions
                if isinstance(a, type(parser._subparsers._actions[-1]))
                and hasattr(a, '_parser_class')
            ]
            if subparsers_actions:
                sub = subparsers_actions[0]
                test_parser = sub.add_parser("_test_interrupt")
                test_parser.set_defaults(func=fake_func)
            return parser

        monkeypatch.setattr(cli_module, "create_parser", patched_create_parser)

        with pytest.raises(SystemExit) as exc_info:
            main(["_test_interrupt"])
        assert exc_info.value.code == 130

    def test_exception_prints_to_stderr_exits_one(self, monkeypatch):
        """Unhandled exceptions should print to stderr and exit 1."""

        def fake_func(args):
            raise RuntimeError("test error")

        import spellbook.cli.main as cli_module

        original_create = cli_module.create_parser

        def patched_create_parser():
            parser = original_create()
            subparsers_actions = [
                a for a in parser._subparsers._actions
                if isinstance(a, type(parser._subparsers._actions[-1]))
                and hasattr(a, '_parser_class')
            ]
            if subparsers_actions:
                sub = subparsers_actions[0]
                test_parser = sub.add_parser("_test_error")
                test_parser.set_defaults(func=fake_func)
            return parser

        monkeypatch.setattr(cli_module, "create_parser", patched_create_parser)

        with pytest.raises(SystemExit) as exc_info:
            main(["_test_error"])
        assert exc_info.value.code == 1


class TestEntryPoint:
    """Test the CLI entry point works as a module."""

    def test_module_invocation(self):
        """spellbook CLI should be invocable."""
        result = subprocess.run(
            [sys.executable, "-m", "spellbook.cli.main", "--help"],
            capture_output=True,
            text=True,
            cwd=tempfile.gettempdir(),
        )
        assert result.returncode == 0
        assert "spellbook" in result.stdout.lower() or "usage" in result.stdout.lower()
