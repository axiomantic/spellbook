"""CLI command: spellbook memory search/export.

Search and export memories from the spellbook memory store.
"""

from __future__ import annotations

import argparse
import csv
import io
import sqlite3

from sqlalchemy.exc import OperationalError as SAOperationalError

from spellbook.cli.formatting import output
from spellbook.core.db import get_db_path


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``memory`` subcommand with ``search`` and ``export``."""
    memory_parser = subparsers.add_parser(
        "memory",
        help="Search and export memories",
    )
    memory_sub = memory_parser.add_subparsers(dest="memory_action")

    # memory search QUERY
    search_parser = memory_sub.add_parser("search", help="FTS5 search across memories")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=10,
        help="Maximum number of results (default: 10)",
    )
    search_parser.add_argument(
        "--namespace",
        default="default",
        help="Project namespace for scoping (default: default)",
    )
    search_parser.add_argument(
        "--scope",
        choices=["project", "global", "all"],
        default="project",
        help="Memory scope: project (default), global, or all",
    )
    search_parser.set_defaults(func=_run_search)

    # memory export
    export_parser = memory_sub.add_parser("export", help="Export all memories")
    export_parser.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Export format (default: json)",
    )
    export_parser.set_defaults(func=_run_export)

    memory_parser.set_defaults(func=_run_memory_help(memory_parser))


def _run_memory_help(parser: argparse.ArgumentParser):
    """Return a function that prints help when no subcommand is given."""
    def _func(args: argparse.Namespace) -> None:
        if not getattr(args, "memory_action", None):
            parser.print_help()
    return _func


def _run_search(args: argparse.Namespace) -> None:
    """Execute ``spellbook memory search QUERY``."""
    json_mode = getattr(args, "json", False)
    db_path = str(get_db_path())

    try:
        from spellbook.memory.tools import do_memory_recall

        result = do_memory_recall(
            db_path=db_path,
            query=args.query,
            namespace=args.namespace,
            limit=args.limit,
            scope=getattr(args, "scope", "project"),
        )
    except (sqlite3.OperationalError, SAOperationalError, FileNotFoundError, OSError):
        result = {"memories": [], "count": 0, "query": args.query}

    if json_mode:
        output(result, json_mode=True)
    else:
        memories = result.get("memories", [])
        if not memories:
            print(f"No memories found for: {args.query}")
        else:
            rows = []
            for mem in memories:
                rows.append({
                    "id": mem.get("id", ""),
                    "content": str(mem.get("content", ""))[:80],
                    "score": f"{mem.get('score', 0):.2f}" if mem.get("score") else "",
                })
            output(rows, headers=["id", "content", "score"])


def _run_export(args: argparse.Namespace) -> None:
    """Execute ``spellbook memory export``."""
    json_mode = getattr(args, "json", False) or args.format == "json"
    db_path = get_db_path()

    memories: list[dict] = []
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT id, content, namespace, importance, access_count, "
                "created_at, last_accessed FROM memories "
                "WHERE deleted = 0 ORDER BY created_at DESC"
            )
            memories = [dict(row) for row in cur.fetchall()]
            conn.close()
        except sqlite3.OperationalError:
            memories = []

    if args.format == "csv" and not json_mode:
        if not memories:
            print("No memories to export.")
            return
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=memories[0].keys())
        writer.writeheader()
        writer.writerows(memories)
        print(buf.getvalue(), end="")
    else:
        output(memories, json_mode=True)


def run(args: argparse.Namespace) -> None:
    """Execute the memory command (dispatches to subcommand)."""
    if hasattr(args, "func"):
        args.func(args)
