"""spellbook-planlint — CLI entry point. Argv in, exit code out. No rule
logic lives here; every rule decision is made by spellbook.planlint.api.
"""

import argparse
import sys
from pathlib import Path

from spellbook.planlint.api import Phase, lint_path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="spellbook-planlint")
    parser.add_argument("plan", help="path to a spellbook implementation plan")
    parser.add_argument(
        "--repo-root", default=None, help="repository root for Files: path checks"
    )
    parser.add_argument(
        "--phase",
        choices=[p.value for p in Phase],
        default=Phase.REVIEW.value,
        help="which call-site phase to lint under (default: review)",
    )
    args = parser.parse_args(argv)

    # COERCE AT THE BOUNDARY. argparse hands back a `str`, and
    # RuleContext.repo_root is documented `Path | None` while rules/files.py
    # does `ctx.repo_root / entry.path`, which raises TypeError on a str. That
    # TypeError would be caught by run_rules()'s barrier and reported as a rule
    # CRASH — a caller bug wearing a plan defect's costume. This is the only
    # place a string can enter, so this is the only place that converts.
    repo_root = Path(args.repo_root) if args.repo_root else None

    report = lint_path(args.plan, phase=Phase(args.phase), repo_root=repo_root)
    sys.stdout.write(report.report())

    if not report.linted:
        return 1 if "unreadable" in report.skip_reason or "not UTF-8" in report.skip_reason else 0
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
