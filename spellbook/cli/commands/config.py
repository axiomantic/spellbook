"""CLI command: spellbook config get/set.

Read and write configuration values from ``spellbook.json``.
"""

from __future__ import annotations

import argparse
import json

from spellbook.cli.formatting import output
from spellbook.core.config import config_get, config_set, get_config_path


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``config`` subcommand with ``get`` and ``set``."""
    config_parser = subparsers.add_parser(
        "config",
        help="Read or write spellbook configuration values",
    )
    config_sub = config_parser.add_subparsers(dest="config_action")

    # config get [KEY]
    get_parser = config_sub.add_parser("get", help="Read config value(s)")
    get_parser.add_argument(
        "key",
        nargs="?",
        default=None,
        help="Config key to read (omit to show all)",
    )
    get_parser.set_defaults(func=_run_get)

    # config set KEY VALUE
    set_parser = config_sub.add_parser("set", help="Set a config value")
    set_parser.add_argument("key", help="Config key")
    set_parser.add_argument("value", help="Value to set")
    set_parser.set_defaults(func=_run_set)

    config_parser.set_defaults(func=_run_config_help(config_parser))


def _run_config_help(parser: argparse.ArgumentParser):
    """Return a function that prints help when no subcommand is given."""
    def _func(args: argparse.Namespace) -> None:
        if not getattr(args, "config_action", None):
            parser.print_help()
    return _func


def _run_get(args: argparse.Namespace) -> None:
    """Execute ``spellbook config get [KEY]``."""
    json_mode = getattr(args, "json", False)

    if args.key is not None:
        value = config_get(args.key)
        output({args.key: value}, json_mode=json_mode)
    else:
        # Show all config
        config_path = get_config_path()
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        else:
            data = {}
        output(data, json_mode=json_mode)


def _run_set(args: argparse.Namespace) -> None:
    """Execute ``spellbook config set KEY VALUE``."""
    json_mode = getattr(args, "json", False)

    # Try to parse value as JSON (for booleans, numbers, etc.)
    try:
        parsed_value = json.loads(args.value)
    except (json.JSONDecodeError, ValueError):
        parsed_value = args.value

    result = config_set(args.key, parsed_value)
    output({args.key: parsed_value, "status": result.get("status", "ok")}, json_mode=json_mode)


def run(args: argparse.Namespace) -> None:
    """Execute the config command (dispatches to subcommand)."""
    if hasattr(args, "func"):
        args.func(args)
