#!/usr/bin/env python3
"""Develop Gate Ledger: persistent state for the develop skill.

The develop skill (skills/develop/SKILL.md) describes a "develop_gate_ledger"
that records per-task gate completion and ceremony selection so a resumed
session can re-assert the remaining gates instead of declaring "done"
prematurely. The skill defines the shape in TypeScript; this module is
the Python reference implementation for reading and writing that shape
to a persistent state file.

State file location: ``$SPELLBOOK_DEV_DIR/develop_gate_ledger.json``,
defaulting to a PER-PROJECT file under
``~/.local/spellbook/develop_gate_ledger-<project-encoded>.json``, where
``<project-encoded>`` is the current working directory's repo root
encoded per the project-encoded convention (leading ``/`` stripped,
``/`` replaced with ``-``; see ``spellbook.core.path_utils.encode_cwd``).
This keeps two different projects -- or two concurrent sessions in
different projects -- from reading and writing the same ledger file.
The file is JSON for human inspectability -- a developer or subagent
can read it directly without the Python module.

On a host with no resolvable home directory (a Windows CI runner with
none of ``USERPROFILE``/``HOMEDRIVE``/``HOMEPATH`` set), that default
cannot be computed and the invocation REFUSES with an error naming the
remedy: set ``$SPELLBOOK_DEV_DIR``, or pass ``--path``. It does not fall
back to a directory under the cwd. Such a fallback exits 0 while reading
and writing a ledger that is not the project's ledger, which is the
silent-but-wrong failure this module is built to avoid. Only an
invocation that actually needs the default is affected: ``$SPELLBOOK_DEV_DIR``
and ``--path`` both work normally with no home directory, and the module
still imports cleanly there.

## Merge semantics (per the develop skill)

The skill is explicit: writes are MERGE-ONLY, never full overwrite. Two
sibling writers -- the develop skill and the spellbook hooks --
both write to the same state row, and an overwrite from either side
clobbers the other. This module therefore deep-merges on every write:

- Objects: recursively merged key-by-key.
- Strings: replaced wholesale (the skill stores newline-joined scalars
  like ``remaining_gates`` deliberately so they can shrink; a list
  accumulation would break that contract).
- Lists: replaced wholesale.

Because lists are replaced wholesale, ``ceremony_history``, ``blockers``,
and ``groups`` are deliberately MAPS keyed by timestamp or id rather than
lists. All three must ACCUMULATE: a second ceremony archive must not erase
the first, opening blocker B2 must not close B1, and recording group G2's
gate stack must not erase G1's. As lists, every one of those writes would
silently discard the prior entries -- and discard them in exactly the audit
trail that exists to prove a gate ran. As maps, the deep-merge adds the new
key and leaves the siblings alone.

Three fields inside those maps are still lists (``open_rows``,
``open_findings``, ``gates``), and that is correct: they describe the
state at one check and must be able to SHRINK, the same reason
``remaining_gates`` is a newline-joined scalar. Every recorder therefore
writes its list on EVERY status, empty included -- an omitted key cannot
shrink anything, so a re-record would inherit the prior record's entries:
a passing re-record reporting a passed gate that still lists open work,
or a re-record claiming gate coverage it never asserted. One shrink rule
across all three beats three fields with three different semantics -- the
ledger's records must be true, and a record that outlives the assertion
that produced it is not.

Deletion is never part of the contract -- ``_deep_merge`` has no delete.
Anything that must "go away" is expressed as a field instead: a closed
blocker carries ``closed_at`` rather than vanishing. The one operation that
genuinely removes state, ``archive_ceremony`` clearing ``ceremony``, is
therefore an explicit non-merging write (``_write_exact``), not a merge.

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

    # Supersede a locked ceremony so an ABORT-and-re-invoke can relock
    python3 scripts/develop_gate_ledger.py archive-ceremony \
        --reason "operator aborted; re-invoking with a heavier ceremony"

    # Open, then later close, a blocker
    python3 scripts/develop_gate_ledger.py blocker B1 --type decision \
        --description "awaiting operator go/no-go"
    python3 scripts/develop_gate_ledger.py blocker B1 --close

    # Record a per-group boundary gate stack (gate_position: per_group)
    python3 scripts/develop_gate_ledger.py group-gate G1 \
        --status passed --gates 4.4,4.5,4.5.1

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
import subprocess
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# This module's own docstring says "a developer or subagent can read it
# directly", and every doc instructs invoking it as
# `python3 scripts/develop_gate_ledger.py <cmd>` -- a bare invocation with
# no guarantee the `spellbook` package is importable (no venv, no
# PYTHONPATH). `_fallback_encode_cwd` below keeps that documented
# invocation working when the import fails. The shared helper
# (`spellbook.core.path_utils.encode_cwd`) remains the preferred source of
# truth; the two implementations must not drift -- see
# tests/scripts/test_develop_gate_ledger.py::test_fallback_encode_cwd_matches_real_implementation
# and ::test_fallback_encode_cwd_matches_real_implementation_with_git_root,
# which covers the branch production actually takes (resolve_git_root=True).


def _fallback_resolve_toplevel(path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return os.path.normpath(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return path


def _fallback_encode_cwd(cwd: str, resolve_git_root: bool = True) -> str:
    if resolve_git_root:
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                first_line = result.stdout.strip().split("\n")[0]
                if first_line.startswith("worktree "):
                    cwd = os.path.normpath(first_line[len("worktree ") :])
                else:
                    cwd = _fallback_resolve_toplevel(cwd)
            else:
                cwd = _fallback_resolve_toplevel(cwd)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            cwd = _fallback_resolve_toplevel(cwd)
    return cwd.replace("\\", "-").replace("/", "-").lstrip("-")


try:
    from spellbook.core.path_utils import encode_cwd
except ModuleNotFoundError:  # standalone invocation, `spellbook` not on sys.path
    encode_cwd = _fallback_encode_cwd

logger = logging.getLogger(__name__)

def default_state_dir() -> Path:
    """Base directory holding the per-project ledger files.

    Resolved lazily rather than at import time: ``Path.home()`` raises
    ``RuntimeError`` on a host with no resolvable home directory (a
    Windows CI runner with none of ``USERPROFILE``/``HOMEDRIVE``/
    ``HOMEPATH`` set), and computing this at module scope made that
    raise before ``main`` could run -- so even an invocation that never
    consults this default, such as one setting ``$SPELLBOOK_DEV_DIR``
    or passing ``--path``, could not start. Lazy resolution keeps those
    invocations working.

    An invocation that genuinely NEEDS this default and has no home
    REFUSES. The alternative -- defaulting under the cwd -- is the
    silent-but-wrong shape: the command exits 0 while reading and
    writing a ledger that is not the project's ledger, and whichever
    directory it happened to run from silently becomes the state
    location. A refusal naming the remedy is the loud failure.

    Wherever ``Path.home()`` works the path is byte-identical to before.
    """
    try:
        home = Path.home()
    except RuntimeError as exc:
        raise LedgerError(
            "no home directory could be determined, so the default ledger "
            "location cannot be resolved; set $SPELLBOOK_DEV_DIR to the "
            "directory that should hold develop_gate_ledger.json, or pass "
            "--path to name the ledger file explicitly"
        ) from exc
    return home / ".local" / "spellbook"

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
    "gate_position",
)

# ceremony.gate_position has a CLOSED value space. A name guard alone would
# store "per_wave" -- a plausible typo -- and every later reader would treat
# it as a meaningful third mode. The value guard makes the typo fail loudly.
GATE_POSITIONS = ("per_task", "per_group")

# Ceremony fields that may move in ONE direction only once the lock is set,
# mapped to the direction that is allowed. "grow" means no element may be
# dropped; "shrink" means no element may be added.
_MONOTONIC_CEREMONY_FIELDS = {
    "selected": "grow",
    "core": "grow",
    "declined": "shrink",
}

# Blocker kinds, per the develop skill's blocker taxonomy.
BLOCKER_TYPES = ("decision", "work", "external")

# Skills the develop skill dispatches subagents to invoke. A recorded dispatch
# names the ones found in its prompt, which is what lets a phase-verification
# checkbox be decided by a command instead of by the agent's own tick.
#
# The vocabulary is FIXED rather than globbed from ``skills/``: this module is
# documented as runnable standalone (`python3 scripts/develop_gate_ledger.py`)
# with no guarantee that $SPELLBOOK_DIR resolves, and a vocabulary that
# silently empties when the directory is not found would make every lookup
# return "no dispatch recorded" -- a false negative wearing the costume of a
# real check. A stale name here instead fails loudly, because
# tests/scripts/test_develop_gate_ledger.py asserts each one still exists as
# skills/<name>/SKILL.md.
DISPATCH_SKILLS = (
    "auditing-green-mirage",
    "dehallucination",
    "devils-advocate",
    "fact-checking",
    "finishing-a-development-branch",
    "requesting-code-review",
    "reviewing-design-docs",
    "reviewing-impl-plans",
    "test-driven-development",
)

# Upper bound on the stored ``description``. The ledger is an audit trail, not
# a transcript: the full dispatch prompt is deliberately NEVER stored (it can
# carry file contents, credentials, and operator text), and only the skill
# names recognized out of it are.
DESCRIPTION_MAX = 200


def default_ledger_path() -> Path:
    """Compute the per-project default ledger path for the current cwd.

    One ledger file per project (see module docstring "State file
    location"): two different projects, or two concurrent sessions in
    different projects, must not read/write the same ledger file.
    """
    encoded = encode_cwd(os.getcwd())
    return default_state_dir() / f"develop_gate_ledger-{encoded}.json"


def ledger_path() -> Path:
    """Resolve the ledger path, honoring ``$SPELLBOOK_DEV_DIR`` if set.

    ``$SPELLBOOK_DEV_DIR`` (when set) still names an exact directory
    holding a single ``develop_gate_ledger.json``, unchanged from before.
    Only the fallback default changes: it is now per-project rather than
    one fixed global path.
    """
    override = os.environ.get("SPELLBOOK_DEV_DIR")
    if override:
        return Path(override) / "develop_gate_ledger.json"
    return default_ledger_path()


def _utc_now() -> str:
    """Current UTC time as an ISO-8601 second-resolution stamp."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_parent(path: Path) -> None:
    """Create the parent directory for ``path`` if it does not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)


def _deep_merge(base: Any, overlay: Any, _at: str = "") -> Any:
    """Deep-merge ``overlay`` onto ``base`` per the ledger merge contract.

    - dict + dict: per-key merge.
    - scalar + scalar: overlay wins (replacement).
    - list + list: overlay wins (replacement). This is why accumulating
      structures are maps, not lists -- see the module docstring.
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
    return _write_exact(target, merged)


def _write_exact(target: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Write ``data`` to ``target`` atomically, with no merge.

    Every ordinary write goes through ``write_ledger``, which merges. This
    helper exists for the one operation that must REMOVE state --
    ``archive_ceremony`` clearing ``ceremony`` -- which a merge can never
    express, because ``_deep_merge`` has no delete.
    """
    _ensure_parent(target)
    # Write atomically: write to a sibling temp file, then rename.
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(target)
    return data


def set_scalar(field: str, value: Any, *, path: Path | None = None) -> dict[str, Any]:
    """Set a top-level scalar field.

    ``set_scalar`` does not recurse into the ledger's nested structures.
    For ceremony writes use ``set_ceremony_field``; for ``blockers``,
    ``groups``, and ``waves`` use the dedicated recorders, which carry the
    guards that make each entry trustworthy.
    """
    if "/" in field or "." in field:
        raise ValueError(
            f"set_scalar only accepts top-level fields, got {field!r}. "
            "For ceremony writes use set_ceremony_field."
        )
    return write_ledger({field: value}, path=path)


def _ceremony_elements(value: str) -> set[str]:
    """Split a newline-joined ceremony scalar into its elements.

    These fields are newline-joined SCALAR strings, never lists (see the
    ``remaining_gates`` note in the skill: ``_deep_merge`` appends lists but
    replaces scalars). One element is one non-blank, stripped line, so blank
    lines and surrounding whitespace carry no meaning. The result is a SET:
    order carries no meaning either, and a reordering must not read as a
    change.
    """
    return {line.strip() for line in value.splitlines() if line.strip()}


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

    ``gate_position`` is locked by the same stamp. The skill's ledger
    shape says it is "locked with the rest of ceremony at locked_at;
    never changed mid-run", so once ``locked_at`` is set, changing an
    already-recorded ``gate_position`` is refused; ``archive_ceremony``
    remains the sanctioned path. Re-asserting the SAME value is allowed,
    and a first write after the lock is allowed -- the guard refuses a
    reposition, not the recording of the original selection.

    ``selected``, ``core`` and ``declined`` stay writable after the lock,
    but in ONE DIRECTION only. Escalation is permitted mid-run ("the lock
    is a floor, not a ceiling"), so ``selected`` and ``core`` may grow and
    ``declined`` may shrink on promotion. The reverse of each is
    de-escalation and is refused; ``archive_ceremony`` is again the
    sanctioned path. ``promotions`` and the remaining fields are
    unrestricted -- they record history rather than the gate set.
    """
    if name not in CEREMONY_FIELDS:
        raise ValueError(
            f"unknown ceremony field {name!r}; valid: {sorted(CEREMONY_FIELDS)}"
        )
    if name == "gate_position" and value not in GATE_POSITIONS:
        raise ValueError(
            f"invalid ceremony.gate_position {value!r}; "
            f"valid: {', '.join(GATE_POSITIONS)}"
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
    # gate_position is locked WITH the ceremony, not merely alongside it:
    # repositioning after the lock takes the same ABORT-and-re-invoke path
    # as any other ceremony change. Guarding only locked_at would leave the
    # documented lock unenforced for the one field a mid-run session has a
    # motive to change.
    if name == "gate_position" and existing_locked:
        existing_position = current.get("ceremony", {}).get("gate_position")
        if existing_position and existing_position != value:
            raise LedgerError(
                f"refusing to rewrite ceremony.gate_position after the lock: "
                f"existing={existing_position!r} new={value!r} "
                f"(locked_at={existing_locked!r}). Repositioning mid-run is not "
                "a thing: archive-ceremony and re-select in a fresh Phase 0."
            )
    # The gate SET is the thing the lock exists to hold. locked_at and
    # gate_position were guarded; selected/core/declined were not, so the
    # documented "a mid-run request to drop a gate is REFUSED" had no
    # mechanism -- rewriting selected from five gates to one after the lock
    # was accepted silently. These three guards are that mechanism.
    #
    # Direction is per-field: selected and core may only GROW, declined may
    # only SHRINK, because growing declined removes a gate from the run by
    # the back door. declined shrinks legitimately on promotion.
    if name in _MONOTONIC_CEREMONY_FIELDS and existing_locked:
        existing_value = current.get("ceremony", {}).get(name)
        if existing_value:
            old = _ceremony_elements(existing_value)
            new = _ceremony_elements(value)
            direction = _MONOTONIC_CEREMONY_FIELDS[name]
            lost = old - new if direction == "grow" else new - old
            if lost:
                verb = "narrow" if direction == "grow" else "widen"
                detail = "dropped" if direction == "grow" else "added"
                raise LedgerError(
                    f"refusing to {verb} ceremony.{name} after the lock: "
                    f"{detail}={sorted(lost)} (locked_at={existing_locked!r}). "
                    "De-escalation mid-run is not a thing: archive-ceremony "
                    "and re-select in a fresh Phase 0."
                )
    return write_ledger({"ceremony": {name: value}}, path=path)


def archive_ceremony(
    reason: str,
    *,
    timestamp: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Archive the current ceremony and clear it so a fresh lock can be set.

    This is the ONLY sanctioned path that may supersede ``locked_at``. The
    lock guard in ``set_ceremony_field`` is untouched: re-invoking develop
    with a different ceremony requires an explicit, reasoned archive, which
    leaves a record. That record is the difference between "the operator
    aborted and re-selected" and "somebody quietly relaxed the gates".

    ``reason`` is REQUIRED and must be non-blank -- an unexplained archive is
    the unaudited path the lock exists to prevent. This mirrors the
    ``status=failed`` requires ``open_rows`` precedent in
    ``record_wave_discipline``.

    ``ceremony_history`` is a MAP keyed by archive timestamp, not a list:
    the merge policy replaces lists wholesale, so a list would lose every
    prior archive on the next sibling write.
    """
    if not reason or not reason.strip():
        raise ValueError(
            "archive_ceremony requires a non-blank reason; an archive with no "
            "stated reason is exactly the unaudited supersede the lock prevents."
        )
    target = path or ledger_path()
    current = read_ledger(target)
    ceremony = current.get("ceremony")
    if not ceremony:
        raise LedgerError(
            "no ceremony to archive: ceremony is absent or empty. "
            "Archiving is for superseding an existing selection."
        )
    stamp = timestamp or _utc_now()
    history = dict(current.get("ceremony_history") or {})
    # Two archives in the same second would collide on the map key and the
    # earlier one would vanish -- silently, and only in the audit trail. Key
    # collisions get a suffix so append-only holds regardless of clock
    # resolution or a caller passing the same explicit --timestamp twice.
    # The suffix is zero-padded: readers sort the history lexically, and an
    # unpadded "#10" sorts before "#2", reading the audit trail out of
    # sequence. Three digits covers any collision count a one-second clock
    # tick can produce; the unsuffixed first key sorts before all of them.
    key = stamp
    n = 2
    while key in history:
        key = f"{stamp}#{n:03d}"
        n += 1
    history[key] = {
        "reason": reason.strip(),
        "archived_at": stamp,
        "ceremony": ceremony,
    }
    updated = dict(current)
    updated["ceremony_history"] = history
    updated["ceremony"] = {}
    return _write_exact(target, updated)


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
    # Written UNCONDITIONALLY, empty on passed/n_a. Omitting the key on a
    # passing re-record would leave the previous failure's rows behind --
    # _deep_merge has no delete, so only a list REPLACEMENT can shrink it,
    # and the docstring's "must be able to SHRINK as rows close" contract
    # is exactly what an omitted key breaks.
    entry["open_rows"] = open_rows_list
    return write_ledger({"waves": {wave_id: {"section_24_6_check": entry}}}, path=path)


def record_blocker(
    blocker_id: str,
    *,
    blocker_type: str | None = None,
    description: str | None = None,
    close: bool = False,
    timestamp: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Open or close a blocker under ``blockers.<blocker_id>``.

    ``blocker_type`` is one of ``BLOCKER_TYPES``. An OPEN blocker is one
    with no ``closed_at``; closure sets that field rather than removing the
    entry, because ``_deep_merge`` has no delete and a removed entry would
    be indistinguishable from one that was never opened.

    Only OPENING consumes the type: closure writes ``closed_at`` and nothing
    else, so ``blocker_type`` is required when opening and OPTIONAL when
    closing. When a closing caller supplies one anyway it is checked against
    the stored type rather than ignored -- the flag is accepted as a
    redundant assertion (which the develop skill's documented
    ``--type ... [--close]`` synopsis writes) and a contradicting value means
    the caller has either the wrong id or the wrong type. Discarding it
    silently is the one outcome that hides both.

    ``blockers`` is a MAP keyed by blocker id for the same reason
    ``ceremony_history`` is: the merge policy replaces lists wholesale, and
    blockers must accumulate across sibling writes.
    """
    if blocker_type is not None and blocker_type not in BLOCKER_TYPES:
        raise ValueError(
            f"type must be one of {'/'.join(BLOCKER_TYPES)}, got {blocker_type!r}"
        )
    stamp = timestamp or _utc_now()
    if close:
        current = read_ledger(path)
        existing = (current.get("blockers") or {}).get(blocker_id)
        if not existing:
            raise LedgerError(
                f"no open blocker {blocker_id!r} to close. Closing a blocker "
                "that was never opened would record a gate that never ran."
            )
        stored_type = existing.get("type") if isinstance(existing, dict) else None
        if blocker_type is not None and stored_type != blocker_type:
            raise LedgerError(
                f"type mismatch closing blocker {blocker_id!r}: stored="
                f"{stored_type!r} given={blocker_type!r}. Closing does not "
                "change the type; either the id or the --type is wrong. Omit "
                "--type to close."
            )
        return write_ledger(
            {"blockers": {blocker_id: {"closed_at": stamp}}}, path=path
        )
    if blocker_type is None:
        raise ValueError(
            f"opening blocker {blocker_id!r} requires --type "
            f"({'/'.join(BLOCKER_TYPES)}); the kind of a blocker is recorded "
            "at open time and has no default."
        )
    entry: dict[str, Any] = {"type": blocker_type, "opened_at": stamp}
    if description and description.strip():
        entry["description"] = description.strip()
    return write_ledger({"blockers": {blocker_id: entry}}, path=path)


def record_group_gate(
    group_id: str,
    *,
    status: str,
    gates: Iterable[str] | None = None,
    open_findings: Iterable[str] | None = None,
    timestamp: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Record the boundary gate stack for a group under ``gate_position: per_group``.

    Without this entry, "the boundary gate ran and passed" and "the boundary
    gate never ran" look identical in the ledger -- the silent-failure shape
    ``record_wave_discipline`` exists to close for waves. This is the
    per-group counterpart, and it carries the same false-pass guard:
    ``status="failed"`` requires at least one open finding, because a failure
    with nothing to fix reads exactly like a pass.
    """
    if status not in ("passed", "failed", "n_a"):
        raise ValueError(
            f"status must be one of passed/failed/n_a, got {status!r}"
        )
    findings = list(open_findings or [])
    if status == "failed" and not findings:
        raise ValueError(
            "status=failed requires at least one open finding in open_findings; "
            "an empty open_findings with status=failed would be a false pass."
        )
    entry: dict[str, Any] = {"status": status}
    if timestamp:
        entry["timestamp"] = timestamp
    # Both lists are written unconditionally, empty included -- see
    # record_wave_discipline. `_deep_merge` replaces lists but never deletes
    # keys, so a conditional write cannot SHRINK: the prior record's value
    # survives. For open_findings that means a gate recorded as passed while
    # still listing the previous failure's findings; for gates it means the
    # record claims coverage the re-record never asserted. One shrink rule
    # across all three sibling list fields (gates, open_findings, open_rows)
    # beats three fields with three different semantics.
    entry["gates"] = list(gates or [])
    entry["open_findings"] = findings
    return write_ledger({"groups": {group_id: {"gate_stack": entry}}}, path=path)


def extract_skills(text: str | None) -> list[str]:
    """Which ``DISPATCH_SKILLS`` names appear in ``text``.

    Substring match, deliberately. A develop dispatch prompt names the skill it
    wants invoked ("invoke the reviewing-design-docs skill", a
    ``$SPELLBOOK_DIR/skills/reviewing-design-docs/SKILL.md`` path); a token or
    word-boundary parse would have to model all of those shapes to gain
    nothing. Returns sorted names so a recorded entry is stable to compare.
    """
    if not text:
        return []
    return sorted(name for name in DISPATCH_SKILLS if name in text)


def record_dispatch(
    *,
    subagent_type: str | None = None,
    description: str | None = None,
    skills: Iterable[str] | None = None,
    source: str | None = None,
    timestamp: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Record that a subagent dispatch happened, under ``dispatches.<key>``.

    The point of this record is WHO WRITES IT. An agent that skips a dispatch
    will also skip a self-recorded note of it, or write one falsely -- a record
    authored by the party that would have skipped the step is a checkbox with
    extra steps, which is exactly what the ``[SELF]`` marker in the develop
    skill exists to admit. The intended writer is therefore the ``PostToolUse``
    hook on the ``Task`` tool (``hooks/spellbook_hook.py``), which fires from
    the harness without the agent's cooperation. This function is also exposed
    on the CLI, because a ledger nobody can inspect is not an audit trail.

    ``dispatches`` is a MAP keyed by timestamp for the same reason
    ``ceremony_history`` is: the merge policy replaces lists wholesale, so a
    list would lose every prior dispatch on the next sibling write -- and lose
    them in precisely the audit trail that exists to prove a dispatch ran.
    Keys collide when two dispatches land in the same second (parallel waves
    make that ordinary, not rare), so a collision takes a zero-padded suffix,
    matching ``archive_ceremony``.

    Every field is optional because the hook records what the payload actually
    carried and nothing more. An entry with no ``subagent_type`` and no
    recognized skill still proves a dispatch occurred at a time -- less than
    the caller wanted, but true.
    """
    target = path or ledger_path()
    current = read_ledger(target)
    stamp = timestamp or _utc_now()
    dispatches = dict(current.get("dispatches") or {})
    key = stamp
    n = 2
    while key in dispatches:
        key = f"{stamp}#{n:03d}"
        n += 1
    entry: dict[str, Any] = {"recorded_at": stamp}
    if subagent_type and subagent_type.strip():
        entry["subagent_type"] = subagent_type.strip()[:DESCRIPTION_MAX]
    if description and description.strip():
        entry["description"] = description.strip()[:DESCRIPTION_MAX]
    if source and source.strip():
        entry["source"] = source.strip()[:DESCRIPTION_MAX]
    entry["skills"] = sorted(set(skills or ()))
    return write_ledger({"dispatches": {key: entry}}, path=path)


def find_dispatches(
    *,
    skill: str | None = None,
    since: str | None = None,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Recorded dispatches matching ``skill`` and/or recorded at/after ``since``.

    ``since`` is the field that keeps a per-task checkbox honest. Phase 4 runs
    its gates once per TASK; without a lower bound, one dispatch recorded in
    task 1 would satisfy the same query for every task after it, and the check
    would pass while proving nothing about the task in hand. Comparison is
    lexical, which is exactly right for the ISO-8601 second-resolution stamps
    this module writes, and it also orders the ``#NNN`` collision suffixes
    within their second.
    """
    entries = read_ledger(path).get("dispatches") or {}
    if not isinstance(entries, dict):
        return []
    found = []
    for value in entries.values():
        if not isinstance(value, dict):
            continue
        if skill and skill not in (value.get("skills") or []):
            continue
        if since and str(value.get("recorded_at") or "") < since:
            continue
        found.append(value)
    return sorted(found, key=lambda e: str(e.get("recorded_at") or ""))


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
    try:
        # ledger_path() is inside the try on purpose: resolving the default
        # can itself refuse (no home directory), and that refusal is a
        # user-facing configuration error, not a crash to traceback.
        path = Path(args.path) if args.path else ledger_path()
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
    except ValueError as exc:
        # Value guards (e.g. ceremony.gate_position) raise ValueError. Exit 2
        # to match the unknown-field path: both are "the caller asked for
        # something the ledger does not accept", not a ledger I/O failure.
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"set {args.field}={args.value!r}")
    return 0


def _cmd_archive_ceremony(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else None
    try:
        archive_ceremony(args.reason, timestamp=args.timestamp, path=path)
    except (ValueError, LedgerError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        "ceremony archived to ceremony_history and cleared; "
        "a fresh Phase 0 may now set ceremony.locked_at"
    )
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


def _cmd_blocker(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else None
    try:
        record_blocker(
            args.blocker_id,
            blocker_type=args.type,
            description=args.description,
            close=args.close,
            timestamp=args.timestamp,
            path=path,
        )
    except (ValueError, LedgerError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        f"blocker {args.blocker_id}: "
        f"{'closed' if args.close else f'opened (type={args.type})'}"
    )
    return 0


def _cmd_group_gate(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else None
    gates = [g.strip() for g in args.gates.split(",")] if args.gates else None
    findings = (
        [f.strip() for f in args.open_findings.split(",")]
        if args.open_findings
        else None
    )
    try:
        record_group_gate(
            args.group_id,
            status=args.status,
            gates=gates,
            open_findings=findings,
            timestamp=args.timestamp,
            path=path,
        )
    except (ValueError, LedgerError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"group {args.group_id}: gate_stack status={args.status}")
    return 0


def _cmd_record_dispatch(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else None
    skills = extract_skills(args.prompt) if args.prompt else []
    if args.skill:
        skills = sorted(set(skills) | set(args.skill))
    try:
        record_dispatch(
            subagent_type=args.subagent_type,
            description=args.description,
            skills=skills,
            source=args.source or "cli",
            timestamp=args.timestamp,
            path=path,
        )
    except (ValueError, LedgerError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"dispatch recorded (skills: {', '.join(skills) or 'none recognized'})")
    return 0


def _cmd_dispatches(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else None
    try:
        found = find_dispatches(skill=args.skill, since=args.since, path=path)
    except LedgerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(found, indent=2, sort_keys=True))
    # Exit 1 on no match so the command can BE a checkbox: `... dispatches
    # --skill X && echo ok`. Printing an empty list with exit 0 would make
    # "recorded" and "never happened" the same signal to any caller that reads
    # the status -- the silent-failure shape this record exists to close.
    return 0 if found else 1


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
            "falling back to a per-project file under "
            "~/.local/spellbook/develop_gate_ledger-<project-encoded>.json"
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

    p_ac = sub.add_parser(
        "archive-ceremony",
        help=(
            "Archive the current ceremony into ceremony_history and clear it, "
            "so an ABORT-and-re-invoke can set a fresh lock. The only "
            "sanctioned path that supersedes ceremony.locked_at."
        ),
    )
    p_ac.add_argument(
        "--reason",
        required=True,
        help="Why the ceremony is being superseded. Required and non-blank.",
    )
    p_ac.add_argument(
        "--timestamp",
        default=None,
        help="ISO-8601 archive timestamp (the history key). Default: now, UTC.",
    )
    p_ac.set_defaults(func=_cmd_archive_ceremony)

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

    p_bl = sub.add_parser("blocker", help="Open or close a blocker")
    p_bl.add_argument("blocker_id", metavar="id", help="Blocker identifier")
    p_bl.add_argument(
        "--type",
        default=None,
        choices=BLOCKER_TYPES,
        help=(
            "Blocker kind. Required when opening. Optional with --close, where "
            "it is checked against the stored type instead of being ignored."
        ),
    )
    p_bl.add_argument(
        "--description", default=None, help="Free-form description of the blocker."
    )
    p_bl.add_argument(
        "--close",
        action="store_true",
        help=(
            "Close an existing blocker by setting closed_at. An open blocker "
            "is one with no closed_at; entries are never deleted."
        ),
    )
    p_bl.add_argument(
        "--timestamp",
        default=None,
        help="ISO-8601 timestamp for opened_at/closed_at. Default: now, UTC.",
    )
    p_bl.set_defaults(func=_cmd_blocker)

    p_gg = sub.add_parser(
        "group-gate",
        help="Record the per-group boundary gate stack (gate_position: per_group)",
    )
    p_gg.add_argument("group_id", metavar="group", help="Group identifier")
    p_gg.add_argument(
        "--status",
        required=True,
        choices=("passed", "failed", "n_a"),
        help="Gate-stack status. failed requires --open-findings.",
    )
    p_gg.add_argument(
        "--gates",
        default=None,
        help="Comma-separated gate identifiers run at the boundary (e.g. 4.4,4.5)",
    )
    p_gg.add_argument(
        "--open-findings",
        default=None,
        help="Comma-separated finding identifiers still open when status=failed",
    )
    p_gg.add_argument(
        "--timestamp",
        default=None,
        help="ISO-8601 timestamp. Default: omitted.",
    )
    p_gg.set_defaults(func=_cmd_group_gate)

    p_rd = sub.add_parser(
        "record-dispatch",
        help=(
            "Record a subagent dispatch. Normally written by the PostToolUse "
            "hook on the Task tool, not by hand."
        ),
    )
    p_rd.add_argument(
        "--subagent-type", default=None, help="Subagent type from the Task call."
    )
    p_rd.add_argument(
        "--description", default=None, help="Short description of the dispatch."
    )
    p_rd.add_argument(
        "--prompt",
        default=None,
        help=(
            "Dispatch prompt to scan for skill names. The prompt itself is "
            "NOT stored; only the recognized skill names are."
        ),
    )
    p_rd.add_argument(
        "--skill",
        action="append",
        default=None,
        help="Record a skill name explicitly. Repeatable.",
    )
    p_rd.add_argument(
        "--source", default=None, help="What wrote the record. Default: cli."
    )
    p_rd.add_argument(
        "--timestamp", default=None, help="ISO-8601 timestamp. Default: now, UTC."
    )
    p_rd.set_defaults(func=_cmd_record_dispatch)

    p_dl = sub.add_parser(
        "dispatches",
        help=(
            "List recorded dispatches as JSON. Exits 1 when none match, so the "
            "invocation can serve as a phase-verification check."
        ),
    )
    p_dl.add_argument(
        "--skill", default=None, help="Only dispatches naming this skill."
    )
    p_dl.add_argument(
        "--since",
        default=None,
        help=(
            "Only dispatches recorded at/after this ISO-8601 stamp. Use it for "
            "per-task gates: without it, a dispatch from an earlier task "
            "satisfies the check for every task after it."
        ),
    )
    p_dl.set_defaults(func=_cmd_dispatches)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
