"""Spellbook CLI entry point.

Provides the root argument parser, subcommand registration, and main()
entry point for the ``spellbook`` console script.
"""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import version

_COMMAND_MODULES = (
    "doctor",
    "server",
    "install",
    "update",
    "admin",
    "config",
    "memory",
    "session",
    "events",
)


def create_parser() -> argparse.ArgumentParser:
    """Create the root argument parser with --version and --json flags."""
    parser = argparse.ArgumentParser(
        prog="spellbook",
        description="Spellbook: AI-assistant enhancement toolkit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"spellbook {version('spellbook')}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output in JSON format",
    )

    subparsers = parser.add_subparsers(dest="command")

    # Register subcommands from spellbook.cli.commands.*
    # Use try/except so the CLI works before all command modules exist.
    for module_name in _COMMAND_MODULES:
        try:
            mod = __import__(
                f"spellbook.cli.commands.{module_name}",
                fromlist=["register"],
            )
            mod.register(subparsers)
        except (ImportError, AttributeError):
            pass

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the spellbook CLI.

    Returns the exit code (also calls ``sys.exit``).
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help(sys.stderr)
        sys.exit(2)

    if not hasattr(args, "func"):
        parser.print_help(sys.stderr)
        sys.exit(2)

    try:
        args.func(args)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    return 0


if __name__ == "__main__":
    main()
