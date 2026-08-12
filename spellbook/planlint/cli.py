"""spellbook-planlint — CLI entry point. Argv in, exit code out. No rule
logic lives here; every rule decision is made by spellbook.planlint.api.
"""

import argparse
import sys
from pathlib import Path

from spellbook.planlint.api import SKIP_NOT_UTF8, SKIP_UNREADABLE, Phase, lint_path


def main(argv=None):
    """Exit code contract:
    0 — clean run, no findings (including a legacy/not-a-planlint-schema skip).
    1 — the plan has findings, or the file was unreadable/not UTF-8.
    2 — a usage error (bad argv) OR an internal rule crash.
    Exit code 2 is intentionally overloaded: both cases mean "something is
    wrong with the run itself, not with the plan under review."
    """
    parser = argparse.ArgumentParser(prog="spellbook-planlint")
    parser.add_argument("plan", help="path to a spellbook implementation plan")
    parser.add_argument("--repo-root", default=None, help="repository root for Files: path checks")
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
    repo_root = None
    if args.repo_root is not None:
        if args.repo_root == "":
            parser.error(f"--repo-root {args.repo_root!r} is not an existing directory")
        repo_root = Path(args.repo_root)
        if not repo_root.is_dir():
            parser.error(f"--repo-root {args.repo_root!r} is not an existing directory")

    report = lint_path(args.plan, phase=Phase(args.phase), repo_root=repo_root)

    if not report.linted:
        # A skip is a diagnostic about why nothing was checked, not linter
        # output — it goes to stderr so a piped `> output.txt` never hides it.
        sys.stderr.write(report.report())
        return 1 if report.skip_kind in (SKIP_UNREADABLE, SKIP_NOT_UTF8) else 0

    # A rule CRASH is also a diagnostic (a linter defect, not a plan defect),
    # so the full report — which embeds the crash traceback inline (see
    # PlanLintReport.report()) — is routed to stderr for that run instead of
    # stdout. Findings-only reports (the common case) stay on stdout.
    destination = sys.stderr if report.internal_errors else sys.stdout
    destination.write(report.report())
    # summary_line() is what C1 was missing: LintResult.report() alone can
    # read as "clean" for a rule that was actually SKIPPED (e.g. `files`
    # with no --repo-root). summary_line() states, in one line, how many
    # rules actually decided vs were skipped. It is printed here, on the
    # `report.linted` path only — not unconditionally — because the
    # not-linted branch above already returned before reaching this line.
    sys.stdout.write(report.summary_line() + "\n")

    if report.internal_errors:
        return 2
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
