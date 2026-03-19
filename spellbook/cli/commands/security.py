"""CLI command: spellbook security events.

Query and stream security events from the spellbook database.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from spellbook.cli.formatting import output
from spellbook.core.db import get_db_path


def _get_db_path_str() -> str:
    """Return the database path as a string."""
    return str(get_db_path())


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``security`` subcommand with ``events``."""
    security_parser = subparsers.add_parser(
        "security",
        help="Security event management",
    )
    security_sub = security_parser.add_subparsers(dest="security_action")

    # security events
    events_parser = security_sub.add_parser(
        "events",
        help="Query or stream security events",
    )
    events_parser.add_argument(
        "--severity",
        default=None,
        help="Filter by severity level (e.g. INFO, WARNING, HIGH, CRITICAL)",
    )
    events_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=50,
        help="Maximum number of events (default: 50)",
    )
    events_parser.add_argument(
        "--follow", "-f",
        action="store_true",
        default=False,
        help="Stream events in real-time via WebSocket",
    )
    events_parser.set_defaults(func=_run_events)

    security_parser.set_defaults(func=_run_security_help(security_parser))


def _run_security_help(parser: argparse.ArgumentParser):
    """Return a function that prints help when no subcommand is given."""
    def _func(args: argparse.Namespace) -> None:
        if not getattr(args, "security_action", None):
            parser.print_help()
    return _func


def _run_events(args: argparse.Namespace) -> None:
    """Execute ``spellbook security events``."""
    if getattr(args, "follow", False):
        _run_events_follow(args)
    else:
        _run_events_query(args)


def _run_events_query(args: argparse.Namespace) -> None:
    """Query security events from the database."""
    json_mode = getattr(args, "json", False)
    db_path = _get_db_path_str()

    try:
        from spellbook.security.tools import do_query_events

        result = do_query_events(
            severity=getattr(args, "severity", None),
            limit=args.limit,
            db_path=db_path,
        )
    except Exception:
        result = {"success": True, "events": [], "count": 0}

    events = result.get("events", [])
    count = result.get("count", len(events))

    if json_mode:
        output({"events": events, "count": count}, json_mode=True)
    else:
        if not events:
            print("No security events found.")
        else:
            rows = []
            for evt in events:
                rows.append({
                    "timestamp": evt.get("created_at", ""),
                    "severity": evt.get("severity", ""),
                    "type": evt.get("event_type", ""),
                    "message": str(evt.get("detail", ""))[:60],
                })
            output(rows, headers=["timestamp", "severity", "type", "message"])


def _run_events_follow(args: argparse.Namespace) -> None:
    """Stream security events via WebSocket."""
    json_mode = getattr(args, "json", False)

    try:
        from spellbook.cli.daemon_client import stream_events

        async def _stream():
            try:
                async for event in stream_events():
                    if json_mode:
                        print(json.dumps(event, default=str), flush=True)
                    else:
                        ts = event.get("timestamp", "")
                        etype = event.get("type", event.get("event_type", ""))
                        detail = str(event.get("detail", event.get("message", "")))[:80]
                        print(f"{ts}  {etype:20s}  {detail}", flush=True)
            except KeyboardInterrupt:
                pass

        asyncio.run(_stream())
    except ConnectionError:
        print(
            "Error: Cannot connect to spellbook daemon. "
            "Start it with: spellbook server start",
            file=sys.stderr,
        )
        sys.exit(1)
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


def run(args: argparse.Namespace) -> None:
    """Execute the security command (dispatches to subcommand)."""
    if hasattr(args, "func"):
        args.func(args)
