"""``spellbook doctor`` command.

Runs diagnostic checks and reports results.
"""

from __future__ import annotations

import argparse
import sys

from spellbook.cli.formatting import output
from spellbook.health.doctor import run_checks


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``doctor`` subcommand."""
    parser = subparsers.add_parser(
        "doctor",
        help="Run diagnostic checks",
        description="Run diagnostic checks and report results.",
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    """Execute the doctor command."""
    results = run_checks()

    if getattr(args, "json", False):
        data = {
            "checks": [
                {
                    "name": r.name,
                    "status": r.status,
                    "detail": r.detail,
                    **({"fix": r.fix} if r.fix else {}),
                }
                for r in results
            ]
        }
        output(data, json_mode=True)
    else:
        for r in results:
            status_tag = {
                "pass": "[PASS]",
                "fail": "[FAIL]",
                "warn": "[WARN]",
            }.get(r.status, "[????]")

            print(f"{status_tag} {r.name}: {r.detail}")
            if r.fix and r.status != "pass":
                print(f"       Fix: {r.fix}")

    has_failure = any(r.status == "fail" for r in results)
    if has_failure:
        sys.exit(2)
