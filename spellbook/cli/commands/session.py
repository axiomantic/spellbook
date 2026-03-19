"""CLI command: spellbook session list/export.

List and export Claude Code session data from ~/.claude/projects/.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from spellbook.cli.formatting import output


def _get_projects_dir() -> Path:
    """Return the path to ~/.claude/projects/."""
    return Path.home() / ".claude" / "projects"


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``session`` subcommand with ``list`` and ``export``."""
    session_parser = subparsers.add_parser(
        "session",
        help="List and export Claude Code sessions",
    )
    session_sub = session_parser.add_subparsers(dest="session_action")

    # session list
    list_parser = session_sub.add_parser("list", help="List sessions")
    list_parser.add_argument(
        "--project",
        default=None,
        help="Filter to a specific project slug",
    )
    list_parser.set_defaults(func=_run_list)

    # session export SESSION_ID
    export_parser = session_sub.add_parser("export", help="Export session messages")
    export_parser.add_argument("session_id", help="Session ID to export")
    export_parser.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="Export format (default: json)",
    )
    export_parser.set_defaults(func=_run_export)

    session_parser.set_defaults(func=_run_session_help(session_parser))


def _run_session_help(parser: argparse.ArgumentParser):
    """Return a function that prints help when no subcommand is given."""
    def _func(args: argparse.Namespace) -> None:
        if not getattr(args, "session_action", None):
            parser.print_help()
    return _func


def _run_list(args: argparse.Namespace) -> None:
    """Execute ``spellbook session list``."""
    json_mode = getattr(args, "json", False)
    projects_dir = _get_projects_dir()

    sessions: list[dict] = []

    if not projects_dir.exists():
        output(sessions, json_mode=json_mode)
        return

    project_filter = getattr(args, "project", None)

    for proj_dir in sorted(projects_dir.iterdir()):
        if not proj_dir.is_dir():
            continue

        # Apply project filter if given
        if project_filter and project_filter not in proj_dir.name:
            continue

        for jsonl_file in sorted(proj_dir.glob("*.jsonl")):
            try:
                from spellbook.sessions.parser import list_sessions_with_samples

                results = list_sessions_with_samples(str(proj_dir), limit=50)
                for sess in results:
                    sessions.append({
                        "project": proj_dir.name,
                        "slug": sess.get("slug", ""),
                        "title": sess.get("custom_title", ""),
                        "messages": sess.get("message_count", 0),
                        "last_active": sess.get("last_activity", ""),
                        "path": sess.get("path", ""),
                    })
                break  # list_sessions_with_samples handles all files in dir
            except (FileNotFoundError, OSError):
                continue

    if json_mode:
        output(sessions, json_mode=True)
    else:
        if not sessions:
            print("No sessions found.")
        else:
            display_rows = [
                {
                    "project": s["project"],
                    "slug": s.get("slug") or "",
                    "title": (s.get("title") or "")[:40],
                    "messages": s["messages"],
                    "last_active": s.get("last_active", ""),
                }
                for s in sessions
            ]
            output(display_rows, headers=["project", "slug", "title", "messages", "last_active"])


def _run_export(args: argparse.Namespace) -> None:
    """Execute ``spellbook session export SESSION_ID``."""
    json_mode = getattr(args, "json", False)
    projects_dir = _get_projects_dir()

    # Search for the session file across all projects
    if projects_dir.exists():
        for proj_dir in projects_dir.iterdir():
            if not proj_dir.is_dir():
                continue
            session_file = proj_dir / f"{args.session_id}.jsonl"
            if session_file.exists():
                try:
                    from spellbook.sessions.parser import load_jsonl

                    messages = load_jsonl(str(session_file))
                    output(messages, json_mode=True)
                    return
                except (json.JSONDecodeError, OSError) as exc:
                    output(
                        {"error": f"Failed to parse session: {exc}"},
                        json_mode=True,
                    )
                    return

    output(
        {"error": f"Session not found: {args.session_id}"},
        json_mode=True,
    )


def run(args: argparse.Namespace) -> None:
    """Execute the session command (dispatches to subcommand)."""
    if hasattr(args, "func"):
        args.func(args)
