#!/usr/bin/env python3
"""Develop Gate Ledger: persistent state for the develop skill.

The develop skill (skills/develop/SKILL.md) describes a "develop_gate_ledger"
that records per-task gate completion and ceremony selection so a resumed
session can re-assert the remaining gates instead of declaring "done"
prematurely. The skill defines the shape in TypeScript; this module is
the Python reference implementation for reading and writing that shape
to a persistent state file.

State file location: ``$SPELLBOOK_DEV_DIR/develop_gate_ledger.json``,
defaulting to ``~/.local/spellbook/develop_gate_ledger.json``. The file
is JSON for human inspectability -- a developer or subagent can read it
directly without the Python module.

## Merge semantics (per the develop skill)

The skill is explicit: writes are MERGE-ONLY, never full overwrite. Two
sibling writers -- the develop skill and the spellbook hooks --
both write to the same state row, and an overwrite from either side
clobbers the other. This module therefore deep-merges on every write:

- Objects: recursively merged key-by-key.
- Strings: replaced wholesale (the skill stores newline-joined scalars
  like ``remaining_gates`` deliberately so they can shrink; a list
  accumulation would break that contract).
- Lists: replaced wholesale. The skill does not currently use lists
  inside the ledger; if a future field does, change the policy here
  with an explicit note.

## CLI

The script is also a CLI for inspecting and editing the ledger:

    # Show the full ledger
    python3 scripts/develop_gate_ledger.py show

    # Show just the ceremony
    python3 scripts/develop_gate_ledger.py show --field ceremony

    # Set a scalar field (full overwrite of that key)
    python3 scripts/develop_gate_ledger.py set current_phase 4

    # Mark a wave's §24.6 check as passed
    python3 scripts/develop_gate_ledger.py wave-discipline 3a --status passed

    # Mark a wave's §24.6 check as failed with open rows
    python3 scripts/develop_gate_ledger.py wave-discipline 3a \
        --status failed --open-rows W3a-2,W3a-5

    # Record that the check does not apply, and why
    python3 scripts/develop_gate_ledger.py wave-discipline plan \
        --status n_a --reason "plan has no wave structure"

The CLI is intentionally narrow. The ledger is meant to be WRITTEN by
the orchestrator's own discipline, not poked at from outside. Operations
the skill describes -- "write ceremony.locked_at at Phase 0",
"append gate completion" -- are supported; arbitrary edits are not.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_STATE_DIR = Path.home() / ".local" / "spellbook"
DEFAULT_LEDGER_PATH = DEFAULT_STATE_DIR / "develop_gate_ledger.json"

# Fields the ledger may contain, per skills/develop/SKILL.md
# "Ledger shape (develop_gate_ledger, design §5.3)" section.
# ceremony.* is a record of the one-time ceremony selection (§0.8).
CEREMONY_FIELDS = (
    "locked_at",
    "source",
    "assessment",
    "core",
    "selected",
    "declined",
    "promotions",
)


def ledger_path() -> Path:
    """Resolve the ledger path, honoring ``$SPELLBOOK_DEV_DIR`` if set."""
    override = os.environ.get("SPELLBOOK_DEV_DIR")
    if override:
        return Path(override) / "develop_gate_ledger.json"
    return DEFAULT_LEDGER_PATH


def _ensure_parent(path: Path) -> None:
    """Create the parent directory for ``path`` if it does not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)


def _deep_merge(base: Any, overlay: Any, _at: str = "") -> Any:
    """Deep-merge ``overlay`` onto ``base`` per the ledger merge contract.

    - dict + dict: per-key merge.
    - scalar + scalar: overlay wins (replacement).
    - list + list: overlay wins (replacement; the ledger does not use lists).
    - type mismatch: overlay wins (caller is asserting a new shape), but a
      dict being replaced by a non-dict is WARNED about first.

    The warning covers the one mismatch that destroys structure rather than
    a single value: collapsing ``ceremony: {...}`` to a scalar discards every
    field under it at once, including ``locked_at``, whose whole purpose is to
    be un-rewritable. Scalar-to-scalar replacement is the documented contract
    and stays silent. The write still proceeds -- refusing it would strand a
    ledger that a genuine shape change had already moved on from -- but it
    stops being invisible, which is what makes the loss expensive.
    """
    if isinstance(base, dict) and isinstance(overlay, dict):
        merged = dict(base)
        for k, v in overlay.items():
            where = f"{_at}.{k}" if _at else k
            if k in merged:
                merged[k] = _deep_merge(merged[k], v, where)
            else:
                merged[k] = v
        return merged
    if isinstance(base, dict) and not isinstance(overlay, dict):
        logger.warning(
            "develop_gate_ledger: replacing the object at %r with %s; "
            "%d field(s) are discarded: %s",
            _at or "<root>",
            type(overlay).__name__,
            len(base),
            ", ".join(sorted(map(str, base))) or "(none)",
        )
    return overlay


def read_ledger(path: Path | None = None) -> dict[str, Any]:
    """Read the ledger from ``path`` (default: resolved ledger path).

    A missing or unreadable file returns an empty dict -- the ledger is
    "fresh", not an error. The caller decides whether a fresh ledger is
    legal (it is, at the start of a develop run).
    """
    target = path or ledger_path()
    if not target.exists():
        return {}
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise LedgerError(f"cannot read ledger at {target}: {exc}") from exc
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LedgerError(
            f"ledger at {target} is not valid JSON: {exc}. "
            "Refusing to silently overwrite -- rename the corrupt file "
            "aside and start a new ledger."
        ) from exc
    if not isinstance(data, dict):
        raise LedgerError(
            f"ledger at {target} is not a JSON object (got {type(data).__name__})"
        )
    return data


def write_ledger(
    updates: Mapping[str, Any],
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    """Merge ``updates`` into the existing ledger and write the result.

    Performs a deep-merge per ``_deep_merge``. Returns the new ledger
    contents (the same dict that was written to disk).

    The merge is atomic in the sense of "read-then-write under a single
    process": this module does not implement file locking. The develop
    skill is the only expected writer in normal operation; concurrent
    writers are a design bug, not a runtime condition.
    """
    target = path or ledger_path()
    current = read_ledger(target)
    merged = _deep_merge(current, dict(updates))
    _ensure_parent(target)
    # Write atomically: write to a sibling temp file, then rename.
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(target)
    return merged


def set_scalar(field: str, value: Any, *, path: Path | None = None) -> dict[str, Any]:
    """Set a top-level scalar field.

    The ceremony sub-object is the only nested structure the ledger
    currently uses; ``set_scalar`` does not recurse into it. For
    ceremony writes, use ``set_ceremony_field``.
    """
    if "/" in field or "." in field:
        raise ValueError(
            f"set_scalar only accepts top-level fields, got {field!r}. "
            "For ceremony writes use set_ceremony_field."
        )
    return write_ledger({field: value}, path=path)


def set_ceremony_field(
    name: str,
    value: str,
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    """Set a single field on the ``ceremony`` sub-object.

    ``name`` must be one of ``CEREMONY_FIELDS``. ``locked_at`` is the
    load-bearing field: its presence IS the lock, and it is NEVER
    rewritten once set (skill CRIT-2). ``set_ceremony_field`` honors
    that rule -- a re-set of ``locked_at`` to a different value is
    rejected, matching the skill's "the lock is a floor" semantics.
    """
    if name not in CEREMONY_FIELDS:
        raise ValueError(
            f"unknown ceremony field {name!r}; valid: {sorted(CEREMONY_FIELDS)}"
        )
    current = read_ledger(path)
    existing_locked = (
        current.get("ceremony", {}).get("locked_at") if current else None
    )
    if name == "locked_at" and existing_locked and existing_locked != value:
        raise LedgerError(
            f"refusing to rewrite ceremony.locked_at: existing={existing_locked!r} "
            f"new={value!r}. The lock is set once and never rewritten."
        )
    return write_ledger({"ceremony": {name: value}}, path=path)


def record_wave_discipline(
    wave_id: str,
    *,
    status: str,
    open_rows: Iterable[str] | None = None,
    timestamp: str | None = None,
    reason: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Record the §24.6 wave-discipline check for a wave.

    ``status`` is one of ``"passed"``, ``"failed"``, ``"n_a"``. The
    develop skill requires this entry to exist before any "Wave X done"
    claim may be written -- the merge contract below makes the entry
    itself the gate, the same way ``ceremony.locked_at`` is the gate
    for ceremony changes.

    ``open_rows`` is the list of W<n>- identifiers that were still
    open when the check ran; required when ``status="failed"`` and
    ignored when ``status="passed"`` or ``"n_a"``.

    ``reason`` is optional free-form context. It earns its place on
    ``n_a``: "not applicable" alone does not say WHY, and the point of
    recording n_a at all is that a later reader can tell "the operator
    established this check does not apply here" from "nobody ran it".
    Without the reason, n_a says only the former half.
    """
    if status not in ("passed", "failed", "n_a"):
        raise ValueError(
            f"status must be one of passed/failed/n_a, got {status!r}"
        )
    open_rows_list = list(open_rows or [])
    if status == "failed" and not open_rows_list:
        raise ValueError(
            "status=failed requires at least one open row in open_rows; "
            "an empty open_rows with status=failed would be a false pass."
        )
    entry: dict[str, Any] = {"status": status}
    if timestamp:
        entry["timestamp"] = timestamp
    if reason and reason.strip():
        entry["reason"] = reason.strip()
    if status == "failed":
        entry["open_rows"] = open_rows_list
    return write_ledger({"waves": {wave_id: {"section_24_6_check": entry}}}, path=path)


def wave_discipline_status(
    wave_id: str, *, path: Path | None = None
) -> dict[str, Any] | None:
    """Return the recorded §24.6 entry for a wave, or None if absent."""
    current = read_ledger(path)
    waves = current.get("waves") or {}
    wave = waves.get(wave_id) or {}
    return wave.get("section_24_6_check")


def is_wave_done_claimable(wave_id: str, *, path: Path | None = None) -> bool:
    """Whether a "Wave X done" claim for ``wave_id`` is currently legal.

    True iff ``wave_discipline_status(wave_id)`` exists with
    ``status="passed"``. The develop skill should refuse any wave-done
    claim when this returns False, and should report the recorded
    status (with open rows when status="failed") so the operator
    sees the same evidence the ledger has.
    """
    entry = wave_discipline_status(wave_id, path=path)
    return entry is not None and entry.get("status") == "passed"


# ---- CLI ----------------------------------------------------------------


def _cmd_show(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else ledger_path()
    try:
        data = read_ledger(path)
    except LedgerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.field:
        # Allow dotted lookups: ``ceremony.locked_at``
        cur: Any = data
        for part in args.field.split("."):
            if not isinstance(cur, dict) or part not in cur:
                print(f"(field {args.field!r} not set)")
                return 0
            cur = cur[part]
        print(json.dumps(cur, indent=2, sort_keys=True))
    else:
        print(json.dumps(data, indent=2, sort_keys=True))
    return 0


def _cmd_set(args: argparse.Namespace) -> int:
    try:
        if args.field.startswith("ceremony."):
            name = args.field[len("ceremony."):]
            if name not in CEREMONY_FIELDS:
                print(
                    f"error: unknown ceremony field {name!r}; "
                    f"valid: {sorted(CEREMONY_FIELDS)}",
                    file=sys.stderr,
                )
                return 2
            # Route through set_ceremony_field, not write_ledger: the
            # locked_at rewrite guard lives there, and a CLI that wrote
            # directly would be a hole straight through the lock.
            set_ceremony_field(
                name, args.value, path=Path(args.path) if args.path else None
            )
        else:
            write_ledger({args.field: args.value}, path=Path(args.path) if args.path else None)
    except LedgerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"set {args.field}={args.value!r}")
    return 0


def _cmd_wave_discipline(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else None
    open_rows = [r.strip() for r in args.open_rows.split(",")] if args.open_rows else None
    try:
        record_wave_discipline(
            args.wave,
            status=args.status,
            open_rows=open_rows,
            timestamp=args.timestamp,
            reason=args.reason,
            path=path,
        )
    except (ValueError, LedgerError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    claimable = is_wave_done_claimable(args.wave, path=path)
    print(
        f"wave {args.wave}: §24.6 status={args.status}; "
        f"Wave-done claim {'ALLOWED' if claimable else 'REFUSED'}"
    )
    return 0


class LedgerError(Exception):
    """A ledger operation failed in a way the caller must handle."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="develop_gate_ledger",
        description=(
            "Read/write the develop skill's gate ledger. Most operations "
            "should be performed by the develop skill itself; this CLI "
            "is for inspection and recovery."
        ),
    )
    parser.add_argument(
        "--path",
        default=None,
        help=(
            "Override the ledger file path. Default: "
            "$SPELLBOOK_DEV_DIR/develop_gate_ledger.json, "
            "falling back to ~/.local/spellbook/develop_gate_ledger.json"
        ),
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_show = sub.add_parser("show", help="Print the ledger (or one field)")
    p_show.add_argument(
        "--field", default=None,
        help="Dotted field path (e.g. ceremony.locked_at). Omit for full ledger.",
    )
    p_show.set_defaults(func=_cmd_show)

    p_set = sub.add_parser("set", help="Set a top-level or ceremony.* field")
    p_set.add_argument("field", help="Field name (e.g. current_phase or ceremony.selected)")
    p_set.add_argument("value", help="Value to write (string)")
    p_set.set_defaults(func=_cmd_set)

    p_wd = sub.add_parser(
        "wave-discipline",
        help="Record the §24.6 wave-discipline check for a wave",
    )
    p_wd.add_argument("wave", help="Wave identifier (e.g. 3a)")
    p_wd.add_argument(
        "--status",
        required=True,
        choices=("passed", "failed", "n_a"),
        help="Check status. failed requires --open-rows.",
    )
    p_wd.add_argument(
        "--open-rows",
        default=None,
        help="Comma-separated W<n>- identifiers still open when status=failed",
    )
    p_wd.add_argument(
        "--timestamp",
        default=None,
        help="ISO-8601 timestamp. Default: omitted (caller writes one if needed).",
    )
    p_wd.add_argument(
        "--reason",
        default=None,
        help=(
            "Free-form context for the entry. Most useful with --status n_a, "
            "where it records WHY the check does not apply "
            "(e.g. 'plan has no wave structure')."
        ),
    )
    p_wd.set_defaults(func=_cmd_wave_discipline)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
