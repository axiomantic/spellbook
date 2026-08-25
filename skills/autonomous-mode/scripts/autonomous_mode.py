#!/usr/bin/env python3
"""autonomous_mode: the executable entry point for enforced autonomous mode.

``spellbook/core/autonomous.py`` owns the record the ``Stop`` hook reads.
Nothing could WRITE one: the skill named a Python symbol and left the agent
to improvise an interpreter and guess where the session id comes from. A
guess that misses produces no record, and a session with no record is
allowed to end every turn -- an enabled-but-unwired autonomous mode is
observationally identical to a disabled one, which is the failure shape
``rules/92-core-philosophy.md`` names.

The shape follows ``skills/agent2agent/scripts/agent2agent.py``, the
in-tree precedent for a skill-driven helper: argparse subcommands, one exit
code per outcome, and the session id defaulting to
``$CLAUDE_CODE_SESSION_ID`` exactly as ``commands/a2a.md`` takes it. It is
the right precedent because the two solve the same problem -- a slash
command or skill needs to branch on what happened -- and a second dialect
would be one more thing an agent has to guess at.

``enable`` READS THE RECORD BACK and fails if it is not there. The whole
point of the mode is enforcement; a write whose success is unverified is
how the feature ends up silently off, and the operator would be told they
are in autonomous mode by the one report that never checked.

Exit codes, uniform across subcommands:

    0  the operation succeeded, verified against the record itself
    1  it failed -- the message on stderr says how
    2  usage error
    3  this session is not autonomous (``status`` only, and not an error)

Nothing here raises for an unknowable path or an unreadable record: that is
the module's contract and this is its command line, so a fault prints a
message and sets an exit code.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spellbook.core import autonomous  # noqa: E402

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_NOT_AUTONOMOUS = 3


def _session_id(args: argparse.Namespace) -> str:
    """The session the record is scoped to.

    ``$CLAUDE_CODE_SESSION_ID`` is the harness's own variable and the same
    source ``commands/a2a.md`` uses. Naming it here rather than in prose is
    the point of this file: an agent that has to guess where the id comes
    from writes a record under the wrong key, and nothing downstream can
    tell that from autonomous mode never having been enabled.
    """
    return args.session_id or os.environ.get("CLAUDE_CODE_SESSION_ID", "")


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return EXIT_FAILED


def cmd_enable(args: argparse.Namespace) -> int:
    session_id = _session_id(args)
    if not session_id:
        return _fail(
            "no session id: pass --session-id or export CLAUDE_CODE_SESSION_ID"
        )
    set_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        written = autonomous.write_autonomous_record(
            session_id,
            mode=args.mode,
            philosophy=args.philosophy,
            goal=args.goal,
            set_at=set_at,
        )
    except OSError as exc:
        return _fail(f"could not write the autonomous record: {exc}")
    if not written:
        return _fail(
            "refused: the session id, mode, or philosophy is not valid "
            f"(modes: fully, mostly; philosophies: {', '.join(sorted(autonomous.PHILOSOPHIES))})"
        )
    record = autonomous.read_autonomous_record(session_id)
    if record is None:
        return _fail(
            "the record did not survive its own write-then-read: autonomous "
            "mode is NOT enabled. Tell the operator plainly rather than "
            "reporting the write."
        )
    print(json.dumps(record, indent=2))
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    session_id = _session_id(args)
    record = autonomous.read_autonomous_record(session_id) if session_id else None
    if record is None:
        print("not autonomous", file=sys.stderr)
        return EXIT_NOT_AUTONOMOUS
    print(json.dumps(record, indent=2))
    return EXIT_OK


def cmd_clear(args: argparse.Namespace) -> int:
    session_id = _session_id(args)
    if not session_id:
        return _fail(
            "no session id: pass --session-id or export CLAUDE_CODE_SESSION_ID"
        )
    if not autonomous.clear_autonomous_record(session_id):
        return _fail(
            "the autonomous record could not be removed; the Stop hook will "
            f"keep refusing to end a turn. File: {autonomous._record_path(session_id)}"
        )
    print("cleared")
    return EXIT_OK


def cmd_decide(args: argparse.Namespace) -> int:
    session_id = _session_id(args)
    if not session_id:
        return _fail(
            "no session id: pass --session-id or export CLAUDE_CODE_SESSION_ID"
        )
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    appended = autonomous.append_decision(
        session_id,
        at=at,
        philosophy=args.philosophy or _active_philosophy(session_id),
        decision=args.decision,
        alternatives=args.alternatives,
    )
    if not appended:
        return _fail(
            "the decision was not recorded: this session has no readable "
            "autonomous record, or the record could not be written"
        )
    print("recorded")
    return EXIT_OK


def _active_philosophy(session_id: str) -> str:
    """The philosophy id in force right now, for a decision that omits one.

    Copied in at append time rather than joined later: the active philosophy
    can change mid-session, and a stale join would attribute the decision to
    the wrong one.
    """
    record = autonomous.read_autonomous_record(session_id)
    if record is None:
        return autonomous.DEFAULT_PHILOSOPHY
    return str(record.get("philosophy", autonomous.DEFAULT_PHILOSOPHY))


def cmd_philosophies(_args: argparse.Namespace) -> int:
    """The enum, read from the module at ask time.

    The skill offers these through ``AskUserQuestion``. Printing them from
    the one definition is what keeps the offered list and the id the hook
    names in its block messages from being two lists.
    """
    print(
        json.dumps(
            {
                "default": autonomous.DEFAULT_PHILOSOPHY,
                "philosophies": autonomous.PHILOSOPHIES,
            },
            indent=2,
        )
    )
    return EXIT_OK


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="autonomous_mode.py",
        description="Read and write the per-session autonomous-mode record.",
    )
    sub = p.add_subparsers(dest="command")

    def with_session(parser):
        parser.add_argument(
            "--session-id",
            default="",
            help="defaults to $CLAUDE_CODE_SESSION_ID",
        )
        return parser

    sp_enable = with_session(sub.add_parser("enable"))
    sp_enable.add_argument("--mode", required=True, choices=("fully", "mostly"))
    sp_enable.add_argument(
        "--philosophy", required=True, choices=sorted(autonomous.PHILOSOPHIES)
    )
    sp_enable.add_argument(
        "--goal", required=True, help="the goal in the operator's own words"
    )
    sp_enable.set_defaults(func=cmd_enable)

    with_session(sub.add_parser("status")).set_defaults(func=cmd_status)
    with_session(sub.add_parser("clear")).set_defaults(func=cmd_clear)

    sp_decide = with_session(sub.add_parser("decide"))
    sp_decide.add_argument("--decision", required=True)
    sp_decide.add_argument("--alternatives", required=True)
    sp_decide.add_argument(
        "--philosophy",
        default="",
        help="defaults to the philosophy active in the record right now",
    )
    sp_decide.set_defaults(func=cmd_decide)

    sub.add_parser("philosophies").set_defaults(func=cmd_philosophies)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if not getattr(args, "func", None):
        parser.print_usage(sys.stderr)
        return EXIT_USAGE
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        # The module's contract is that nothing raises at the operator. Its
        # command line inherits that: a traceback here reads as a spellbook
        # crash, and the agent above it would have no exit code to branch on.
        return _fail(f"autonomous mode: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    sys.exit(main())
