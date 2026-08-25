"""Per-session autonomous-mode state.

A ``Stop`` hook reads this module to decide whether a turn is allowed to end.
The record lives at ``<state_dir>/autonomous/<session_id>.json``, following
the ``.open/<session_id>`` pattern the agent2agent bus already uses for
per-session state. Per-session is deliberate: autonomy must not outlive the
conversation that granted it.

Every read degrades to "not autonomous" rather than raising. A hook that
raises takes out the operator's turn, so a missing file, malformed JSON, an
unreadable file, a bad session id, wrong field types, or a partial record all
resolve the same way: as if no record existed. See the same reasoning
documented at ``hooks/spellbook_hook.py:_develop_ledger_path``.

Completion verification is layered on top of this module and is explicitly
limited. It cannot verify that the evidence is true. The artifact path
checks that a claimed-evidence file EXISTS, PARSES, and covers every
declared criterion; it never runs the commands that file names, never
compares their real output to the output recorded beside them, and cannot
tell a genuine transcript from one composed to satisfy the check. The
develop path is one step stronger only because a separate mechanism -- the
gate ledger -- wrote the state it reads; it still trusts whoever recorded
those verdicts. What both paths do is convert a completion claim from a
sentence into a reviewable artifact, so a false claim has to be WRITTEN
DOWN where a human can check it. That is a real improvement and a limited
one, and it is not proof of completion.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from spellbook.core.command_utils import atomic_replace
from spellbook.core.paths import get_data_dir

# Mirrors hooks/spellbook_hook.py::_A2A_SESSION_ID_RE -- the same validation
# dialect the a2a handlers already use before a session id reaches a path
# join. One regex, reused, rather than a second dialect drifting from it.
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

_VALID_MODES = {"fully", "mostly"}

# The rolling-window valve. The Stop hook blocks repeatedly by design, so
# something other than the harness must decide when further blocking cannot
# help. That signal is TIME, not a count: a turn that does real work takes far
# longer than twenty seconds, so BLOCK_WINDOW_LIMIT blocks inside
# BLOCK_WINDOW_SECONDS means the model is ending turns without doing anything,
# and one more refusal will not change that.
#
# The timestamps are wall clock (``time.time()``), not ``time.monotonic()``.
# Monotonic is unusable here: each hook invocation is a separate process, and
# monotonic has no epoch shared across processes or reboots. The wall clock's
# failure modes both resolve safely. A forward jump or a suspended laptop
# widens the measured gap, which reads as "not thrashing" and keeps the gate
# active. A backward jump (NTP step, manual clock set) narrows or inverts it,
# which opens the valve and ALLOWS a stop. That is a spurious allow, never a
# spurious trap -- the same direction every other unknown in this module
# resolves to.
BLOCK_WINDOW_SECONDS = 60.0
BLOCK_WINDOW_LIMIT = 3

# The guiding philosophy an autonomous session runs under. The operator picks
# one when entering autonomous mode; the Stop hook names the active id in every
# block message, which is why the set lives here in code rather than in an
# always-loaded rule file. ``rules/92-core-philosophy.md`` states the DEFAULT
# and points here; it deliberately does not restate this list, so the list can
# grow in one place.
#
# Each value is the one-line meaning of the id, phrased as the standing
# instruction for an unattended decision.
PHILOSOPHIES: dict[str, str] = {
    "build-right": (
        "aim for the most correct, least deferred, most ergonomic, and "
        "easiest-to-understand result"
    ),
    "ship-fast": (
        "take the working solution now, accept known rough edges, record what "
        "was deferred"
    ),
    "minimal-diff": (
        "change as little as possible; match surrounding style rather than "
        "improve it; never refactor adjacent code"
    ),
    "hostile-review": (
        "assume every change is reviewed adversarially: prove guards fail, "
        "verify artifacts rather than signals, claim nothing unverified"
    ),
    "explore-then-commit": (
        "build a throwaway probe first, learn from it, then implement "
        "deliberately"
    ),
}

# The philosophy a session runs under when the operator expresses no
# preference. It is the one ``rules/92-core-philosophy.md`` already states.
DEFAULT_PHILOSOPHY = "build-right"


def _autonomous_dir() -> Path:
    """The directory holding per-session autonomous-mode records."""
    return get_data_dir() / "autonomous"


def _record_path(session_id: str) -> Path | None:
    """Path for ``session_id``'s record, or ``None`` if the id is invalid."""
    if not session_id or not isinstance(session_id, str):
        return None
    if not _SESSION_ID_RE.match(session_id):
        return None
    return _autonomous_dir() / f"{session_id}.json"


def _validate_record(data: Any) -> dict[str, Any] | None:
    """Return ``data`` if it is a well-formed autonomous record, else ``None``.

    Required fields: ``mode`` (``"fully"`` or ``"mostly"``), ``philosophy``
    (an id in ``PHILOSOPHIES``), ``goal`` (string), ``goal_criteria`` (list),
    ``set_at`` (string), ``blocked_stops`` (int). A record missing or
    mistyping any field is treated identically to a missing file -- "not
    autonomous" -- rather than partially trusted.

    A ``decisions`` entry also carries a ``philosophy`` id, and that one is
    checked only for being a string. A decision records which philosophy was
    active HISTORICALLY; if the enum ever loses or renames an id, strict
    validation there would make every session that ever used it read as not
    autonomous, silently disabling enforcement over an entry nothing acts on.
    The record's own ``philosophy`` is different: it is read live to drive the
    current turn, so an id nothing can interpret must fail closed.
    """
    if not isinstance(data, dict):
        return None
    if data.get("mode") not in _VALID_MODES:
        return None
    if data.get("philosophy") not in PHILOSOPHIES:
        return None
    if not isinstance(data.get("goal"), str):
        return None
    if not isinstance(data.get("goal_criteria"), list):
        return None
    if not isinstance(data.get("set_at"), str):
        return None
    if not isinstance(data.get("blocked_stops"), int) or isinstance(
        data.get("blocked_stops"), bool
    ):
        return None
    if not isinstance(data.get("decisions"), list):
        return None
    # Optional. Absent and null both mean "no evidence artifact declared",
    # which the artifact predicate reads as not complete. Only a PRESENT
    # non-string is malformed.
    if data.get("evidence_path") is not None and not isinstance(
        data.get("evidence_path"), str
    ):
        return None
    # Optional, for the same reason ``evidence_path`` is: records written
    # before the valve existed have no timestamps, and an absent list means
    # "no blocks recorded yet". A PRESENT value that is not a list of finite
    # numbers is malformed, and malformed valve state makes the whole record
    # read as "not autonomous" -- which ALLOWS the stop. Broken bookkeeping
    # must never be what traps a session.
    block_times = data.get("block_times")
    if block_times is not None:
        if not isinstance(block_times, list):
            return None
        for stamp in block_times:
            if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
                return None
            if stamp != stamp or stamp in (float("inf"), float("-inf")):
                return None
    for entry in data["decisions"]:
        if not isinstance(entry, dict):
            return None
        if not all(
            isinstance(entry.get(k), str)
            for k in ("at", "philosophy", "decision", "alternatives")
        ):
            return None
    return data


def read_autonomous_record(session_id: str) -> dict[str, Any] | None:
    """Return the autonomous-mode record for ``session_id``, or ``None``.

    ``None`` means "treat this session as not autonomous" -- it is returned
    for an invalid session id, a missing file, unreadable file, malformed
    JSON, or a well-formed-JSON-but-wrong-shape record. This function never
    raises.
    """
    path = _record_path(session_id)
    if path is None:
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return _validate_record(data)


def write_autonomous_record(
    session_id: str,
    *,
    mode: str,
    philosophy: str,
    goal: str,
    goal_criteria: list[str],
    set_at: str,
    blocked_stops: int = 0,
    decisions: list[dict[str, str]] | None = None,
    evidence_path: str | None = None,
    block_times: list[float] | None = None,
) -> bool:
    """Atomically write the autonomous-mode record for ``session_id``.

    ``goal_criteria`` may be empty, which means develop owns completion;
    ``evidence_path`` names the evidence artifact the non-develop completion
    path reads, and is ``None`` when no artifact has been declared yet.

    Returns ``True`` on success, ``False`` if ``session_id`` is invalid or
    the record fields fail validation. Never raises for those cases; genuine
    filesystem errors (e.g. a read-only state directory) still propagate,
    since a write initiated by the operator's own request should not fail
    silently.
    """
    path = _record_path(session_id)
    if path is None:
        return False
    record = {
        "mode": mode,
        "philosophy": philosophy,
        "goal": goal,
        "goal_criteria": goal_criteria,
        "set_at": set_at,
        "blocked_stops": blocked_stops,
        "decisions": decisions if decisions is not None else [],
        "evidence_path": evidence_path,
        "block_times": block_times if block_times is not None else [],
    }
    if _validate_record(record) is None:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    fd_tmp, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    fd_closed = False
    try:
        os.write(fd_tmp, json.dumps(record, indent=2).encode("utf-8"))
        os.close(fd_tmp)
        fd_closed = True
        atomic_replace(tmp_path, str(path))
    except BaseException:
        if not fd_closed:
            os.close(fd_tmp)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return True


def clear_autonomous_record(session_id: str) -> None:
    """Remove the autonomous-mode record for ``session_id``, if any.

    Idempotent: a missing record, or an invalid session id, is a silent
    no-op. Used by the escape-phrase handler (Task 4) and by cleanup after
    completion.
    """
    path = _record_path(session_id)
    if path is None:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _write_autonomous_record_or_none(session_id: str, **fields: Any) -> bool | None:
    """Hook-safe wrapper around ``write_autonomous_record``.

    ``write_autonomous_record`` is deliberately allowed to propagate genuine
    filesystem errors (read-only state dir, ENOSPC, EACCES) because it is
    operator-initiated: someone asked to enter autonomous mode and must
    learn if it did not stick. ``record_blocked_stop`` and
    ``append_decision`` are Stop-hook-initiated and carry the opposite
    contract -- they must never raise, because their caller is the hook that
    gates the end of the operator's turn. Routing both through one function
    can only honor one of those two contracts, so this wrapper is the seam:
    it catches exactly the ``OSError`` family a filesystem fault raises and
    turns it into ``None`` ("not autonomous"), while validation failures
    (``False`` return, no exception) pass through unchanged.
    """
    try:
        return write_autonomous_record(session_id, **fields)
    except OSError:
        return None


def recent_block_times(record: Any) -> list[float]:
    """The recorded block timestamps in ``record``, oldest first.

    An absent, null, or non-list value yields an empty list. Never raises.
    """
    if not isinstance(record, dict):
        return []
    stamps = record.get("block_times")
    if not isinstance(stamps, list):
        return []
    return [
        float(s)
        for s in stamps
        if not isinstance(s, bool) and isinstance(s, (int, float))
    ]


def thrash_valve_open(record: Any, *, now: float) -> bool:
    """Whether ``BLOCK_WINDOW_LIMIT`` blocks fall inside the rolling window.

    ``now`` is passed in rather than read here so callers -- and tests --
    control the clock explicitly.

    The valve counts blocks already ISSUED. It can therefore first open on
    the stop AFTER the limit is reached: there is no way to hold three
    recorded blocks without the third having been issued. Reading the
    prospective current block into the count would open it one stop earlier
    and refuse only twice, which is not the behaviour the constant names.

    The edge is inclusive -- a span of exactly ``BLOCK_WINDOW_SECONDS``
    counts as inside the window -- because the valve's two failure
    directions are not symmetric: opening one moment early costs one
    allowed stop, while refusing to open holds a thrashing session.
    """
    stamps = recent_block_times(record)
    if len(stamps) < BLOCK_WINDOW_LIMIT:
        return False
    oldest_in_window = sorted(stamps)[-BLOCK_WINDOW_LIMIT]
    return (now - oldest_in_window) <= BLOCK_WINDOW_SECONDS


def record_blocked_stop(session_id: str, *, now: float | None = None) -> int | None:
    """Record one blocked stop: bump the counter AND stamp the window.

    ``blocked_stops`` is a bare lifetime counter and cannot answer a
    windowed question; the timestamps cannot answer "how many times has this
    session been held". They measure different things, so both are kept.

    Only the most recent ``BLOCK_WINDOW_LIMIT`` timestamps are persisted.
    The list would otherwise grow for the life of the session, and an entry
    older than the ``BLOCK_WINDOW_LIMIT``-th most recent can never change the
    valve's verdict.

    Returns the new ``blocked_stops`` count, or ``None`` on the same "not
    autonomous" degradation as ``read_autonomous_record`` -- an invalid
    session id, a missing file, a malformed record, or a filesystem error on
    write. Never raises.
    """
    record = read_autonomous_record(session_id)
    if record is None:
        return None
    stamp = time.time() if now is None else now
    stamps = (recent_block_times(record) + [stamp])[-BLOCK_WINDOW_LIMIT:]
    new_count = record["blocked_stops"] + 1
    ok = _write_autonomous_record_or_none(
        session_id,
        mode=record["mode"],
        philosophy=record["philosophy"],
        goal=record["goal"],
        goal_criteria=record["goal_criteria"],
        set_at=record["set_at"],
        blocked_stops=new_count,
        decisions=record["decisions"],
        evidence_path=record.get("evidence_path"),
        block_times=stamps,
    )
    if not ok:
        return None
    return new_count


def append_decision(
    session_id: str,
    *,
    at: str,
    philosophy: str,
    decision: str,
    alternatives: str,
) -> bool:
    """Append one unattended-decision entry to ``session_id``'s record.

    In ``fully`` autonomous mode, each unattended decision is appended here
    instead of announced in the turn, so it stays reviewable without
    spending output. ``philosophy`` is the id active AT THE MOMENT the
    decision was made, copied in by the caller -- it is never read back from
    the record later, because the active philosophy can change mid-session
    and a stale join would misattribute the decision to the wrong one.

    Degrades like the rest of this module: appending to a session with no
    record, a malformed one, or one that hits a filesystem error on write,
    is a silent no-op that returns ``False`` ("not autonomous"), never an
    exception -- the caller is a Stop hook and must not be taken out by a
    bookkeeping failure. The append is atomic via the same
    read-modify-write-through-``write_autonomous_record`` path used by
    ``record_blocked_stop``, so a torn write cannot corrupt the record
    the hook reads.
    """
    record = read_autonomous_record(session_id)
    if record is None:
        return False
    entry = {
        "at": at,
        "philosophy": philosophy,
        "decision": decision,
        "alternatives": alternatives,
    }
    new_decisions = record["decisions"] + [entry]
    ok = _write_autonomous_record_or_none(
        session_id,
        mode=record["mode"],
        philosophy=record["philosophy"],
        goal=record["goal"],
        goal_criteria=record["goal_criteria"],
        set_at=record["set_at"],
        blocked_stops=record["blocked_stops"],
        decisions=new_decisions,
        evidence_path=record.get("evidence_path"),
        block_times=record.get("block_times"),
    )
    return bool(ok)


# ---- completion verification (Task 3) -------------------------------------
#
# Two sources, checked in this order: the develop gate ledger when one exists
# for the project, and otherwise the evidence artifact named by the record.
# Every unknown -- no ledger, unreadable ledger, missing artifact,
# unparseable artifact, absent criteria -- resolves to NOT complete. The
# asymmetry is deliberate and load-bearing: a false negative costs one extra
# block that the escape phrase clears, while a false positive silently
# disables enforcement and looks exactly like a working hook.


def _develop_ledger_module() -> Any:
    """Import ``scripts/develop_gate_ledger``, or ``None`` if unavailable.

    Imported inside the function rather than at module top level on purpose.
    ``scripts/`` is not a package and is not on ``sys.path`` outside pytest
    (``pyproject.toml`` puts it there for tests only), so a top-level import
    would need the same ``sys.path`` mutation at import time and would make
    THIS module unimportable wherever it failed -- taking the Stop hook's
    state layer down with it. As a degrading optional dependency it belongs
    behind a call.
    """
    root = Path(__file__).resolve().parent.parent.parent
    scripts_dir = root / "scripts"
    try:
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        import develop_gate_ledger

        return develop_gate_ledger
    except Exception:
        return None


# The ledger's ``current_phase`` value space is enumerated in
# skills/develop/references/ledger-cli.md: "0" | "1" | "1.5" | "2" | "3" |
# "4" | "fast-path". "4" is the last numbered phase (implementation) and
# "fast-path" is the zero-flag path's own terminal, so these two are the
# phases from which a run can finish. Any other value -- including one added
# later that this set does not know -- reads as "not finished", which is the
# conservative direction.
DEVELOP_FINISHING_PHASES = frozenset({"4", "fast-path"})


def _has_failed_verdict(ledger: dict[str, Any]) -> bool:
    """Whether any recorded wave or group check carries ``status="failed"``.

    These are the only per-check VERDICTS the ledger stores. A malformed
    entry counts as failed: an unreadable verdict is an unknown, and an
    unknown must not read as a pass.
    """
    for key, inner in (("waves", "section_24_6_check"), ("groups", "gate_stack")):
        container = ledger.get(key)
        if container is None:
            continue
        if not isinstance(container, dict):
            return True
        for entry in container.values():
            if not isinstance(entry, dict):
                return True
            check = entry.get(inner)
            if check is None:
                continue
            if not isinstance(check, dict):
                return True
            if check.get("status") == "failed":
                return True
    return False


def develop_completion_verified(ledger_path: Path) -> bool:
    """Whether the develop run recorded at ``ledger_path`` is finished.

    True only when BOTH hold: every gate in ``ceremony.selected`` has left
    the ``remaining_gates`` run-queue with no failed verdict recorded against
    the run, AND ``current_phase`` is one of ``DEVELOP_FINISHING_PHASES``.
    Both, not either -- a drained queue mid-run and a finishing phase with
    gates still queued are each a partial run.

    The ledger is read through ``scripts/develop_gate_ledger``, which owns
    the schema and refuses malformed state, rather than hand-parsed here.
    Its refusals (``LedgerError``) and every other failure resolve to
    ``False``. Never raises.
    """
    module = _develop_ledger_module()
    if module is None:
        return False
    try:
        ledger = module.read_ledger(ledger_path)
        if not isinstance(ledger, dict) or not ledger:
            return False
        if ledger.get("current_phase") not in DEVELOP_FINISHING_PHASES:
            return False
        ceremony = ledger.get("ceremony")
        if not isinstance(ceremony, dict):
            return False
        # ``_ceremony_elements`` is the ledger module's own splitter for its
        # newline-joined scalars. Reused rather than re-implemented because
        # it carries the refusal that matters here: a list where a scalar
        # belongs raises instead of silently comparing as a set of one.
        selected = module._ceremony_elements(
            ceremony.get("selected"), source="ceremony.selected"
        )
        remaining = module._ceremony_elements(
            ledger.get("remaining_gates"), source="remaining_gates"
        )
        if selected & remaining:
            return False
        return not _has_failed_verdict(ledger)
    except Exception:
        return False


def _artifact_covered_criteria(payload: Any) -> set[str] | None:
    """The criteria the evidence artifact actually documents, or ``None``.

    The artifact is a JSON object with a ``criteria`` list; each entry names
    a ``criterion`` and carries the ``command`` that was run for it and that
    command's ``output``. An entry naming a criterion with no command is not
    evidence and contributes no coverage. ``None`` means the payload is not
    in that shape at all.
    """
    if not isinstance(payload, dict):
        return None
    entries = payload.get("criteria")
    if not isinstance(entries, list):
        return None
    covered: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        criterion = entry.get("criterion")
        command = entry.get("command")
        output = entry.get("output")
        if not isinstance(criterion, str) or not criterion.strip():
            continue
        if not isinstance(command, str) or not command.strip():
            continue
        if not isinstance(output, str):
            continue
        covered.add(criterion.strip())
    return covered


def artifact_completion_verified(record: Any) -> bool:
    """Whether ``record``'s evidence artifact covers every declared criterion.

    True only when ``goal_criteria`` is non-empty, ``evidence_path`` names a
    file that EXISTS and PARSES as the documented artifact shape, and every
    declared criterion appears in it with a command and that command's
    output. A criterion present in ``goal_criteria`` but absent from the
    artifact means not complete. Never raises.
    """
    if not isinstance(record, dict):
        return False
    criteria = record.get("goal_criteria")
    if not isinstance(criteria, list) or not criteria:
        return False
    declared = set()
    for item in criteria:
        if not isinstance(item, str) or not item.strip():
            return False
        declared.add(item.strip())
    evidence_path = record.get("evidence_path")
    if not isinstance(evidence_path, str) or not evidence_path.strip():
        return False
    try:
        raw = Path(evidence_path).read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False
    covered = _artifact_covered_criteria(payload)
    if covered is None:
        return False
    return declared <= covered


def completion_verified(record: Any, *, ledger_path: Path | None = None) -> bool:
    """Whether this session's project goal is mechanically verified complete.

    The develop ledger wins when one exists for the project: inside a develop
    run the ledger is the completion authority, and falling through to the
    artifact would let a session declare itself done around a run whose gates
    are still queued. Only when no ledger exists is the evidence artifact
    consulted.

    An autonomous record with an EMPTY ``goal_criteria`` and no develop
    ledger is NOT complete, and that is a decision rather than an accident of
    control flow. Empty criteria mean "develop owns completion" (see
    ``write_autonomous_record``); with no ledger there is no completion
    authority at all, so nothing can ever verify the claim. Reading it as
    vacuously complete would make the cheapest possible record -- autonomous
    mode with no criteria -- the one that ends the first turn.

    Never raises.
    """
    try:
        if ledger_path is not None and Path(ledger_path).is_file():
            return develop_completion_verified(Path(ledger_path))
    except OSError:
        return False
    return artifact_completion_verified(record)
