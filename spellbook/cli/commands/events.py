"""CLI command: spellbook events.

Real-time event streaming from the spellbook daemon via WebSocket.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys



def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``events`` subcommand."""
    events_parser = subparsers.add_parser(
        "events",
        help="Stream real-time events from the spellbook daemon",
    )
    events_parser.add_argument(
        "--follow", "-f",
        action="store_true",
        default=True,
        help="Stream events in real-time (default: true)",
    )
    events_parser.set_defaults(func=_run_events)


def _run_events(args: argparse.Namespace) -> None:
    """Execute ``spellbook events``."""
    json_mode = getattr(args, "json", False)

    try:
        async def _stream():
            from spellbook.cli.daemon_client import stream_events  # lazy import

            try:
                async for event in stream_events():
                    if json_mode:
                        print(json.dumps(event, default=str), flush=True)
                    else:
                        ts = event.get("timestamp", "")
                        etype = event.get("type", event.get("event_type", "unknown"))
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
    """Execute the events command."""
    _run_events(args)
