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

Nothing here judges whether the work is DONE. The Stop hook does not decide
that and this module does not help it: the record says a session is
autonomous, the rolling-window valve says whether the session has already
insisted it is finished, and the model itself answers the rest. An earlier
design verified completion from a gate ledger or a declared evidence
artifact; it could never verify that the evidence was true, only that a
claim had been written down, and it is gone.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from spellbook.core.command_utils import atomic_replace
from spellbook.core.compat import CrossPlatformLock
from spellbook.core.paths import get_data_dir

# Mirrors hooks/spellbook_hook.py::_A2A_SESSION_ID_RE -- the same validation
# dialect the a2a handlers already use before a session id reaches a path
# join. One regex, reused, rather than a second dialect drifting from it.
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

_VALID_MODES = {"fully", "mostly"}

# The rolling-window valve. The Stop hook blocks repeatedly by design, so
# something other than the harness must decide when further blocking cannot
# help. That signal is TIME, not a count: a turn that does real work takes
# longer than the window allows per block, so BLOCK_WINDOW_LIMIT blocks inside
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
    (an id in ``PHILOSOPHIES``), ``goal`` (string), ``set_at`` (string),
    ``blocked_stops`` (int), ``decisions`` (list). A record missing or
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
    if not isinstance(data.get("set_at"), str):
        return None
    if not isinstance(data.get("blocked_stops"), int) or isinstance(
        data.get("blocked_stops"), bool
    ):
        return None
    if not isinstance(data.get("decisions"), list):
        return None
    # ``block_times`` is optional: an absent list means "no blocks recorded
    # yet". A PRESENT value that is not a list of usable timestamps is
    # malformed, and malformed valve state makes the whole record read as
    # "not autonomous" -- which ALLOWS the stop. Broken bookkeeping must
    # never be what traps a session.
    #
    # "Usable" is checked by performing the conversion the readers actually
    # do rather than by testing for the shapes known to break it. An int
    # carries no infinity to test for, so a NaN/inf check passes ``10**400``
    # and the OverflowError then lands inside ``record_blocked_stop``, which
    # documents that it never raises. Rejecting here is the right end: a
    # stamp that cannot become a float is not a timestamp, and the whole
    # record failing validation resolves to ALLOW, the direction every
    # unknown in this module resolves to. Repairing it at the point of use
    # would instead keep a record whose bookkeeping is already known corrupt.
    block_times = data.get("block_times")
    if block_times is not None:
        if not isinstance(block_times, list):
            return None
        for stamp in block_times:
            if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
                return None
            try:
                as_float = float(stamp)
            except (OverflowError, ValueError):
                return None
            if as_float != as_float or as_float in (float("inf"), float("-inf")):
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
    for an invalid session id, a missing file, unreadable file, bytes that
    are not UTF-8, malformed JSON, or a well-formed-JSON-but-wrong-shape
    record. This function never raises.

    ``ValueError`` is caught alongside ``OSError`` on the read because
    ``read_text(encoding="utf-8")`` raises ``UnicodeDecodeError`` -- a
    ``ValueError``, not an ``OSError`` -- on a record that is not valid
    UTF-8. Only the hook's blanket catch stood between that and the
    operator's turn, and the autonomous-mode skill calls this module
    directly, with no such catch.
    """
    path = _record_path(session_id)
    if path is None:
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return _validate_record(data)


def write_autonomous_record(
    session_id: str,
    *,
    mode: str,
    philosophy: str,
    goal: str,
    set_at: str,
    blocked_stops: int = 0,
    decisions: list[dict[str, str]] | None = None,
    block_times: list[float] | None = None,
) -> bool:
    """Atomically write the autonomous-mode record for ``session_id``.

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
        "set_at": set_at,
        "blocked_stops": blocked_stops,
        "decisions": decisions if decisions is not None else [],
        "block_times": block_times if block_times is not None else [],
    }
    if _validate_record(record) is None:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    fd_tmp, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    fd_closed = False
    try:
        # ``os.write`` may write FEWER bytes than it was given. On a full
        # filesystem that turns the atomic replace into a lie: a truncated
        # record becomes visible in one step, and every later read sees
        # invalid JSON. The loop writes the whole payload or raises, and the
        # fsync makes it durable BEFORE the replace, so a crash between the
        # two leaves the old record rather than an empty new one.
        payload = json.dumps(record, indent=2).encode("utf-8")
        written = 0
        while written < len(payload):
            n = os.write(fd_tmp, payload[written:])
            if n <= 0:
                raise OSError(
                    f"short write to {tmp_path}: {written} of {len(payload)} bytes"
                )
            written += n
        os.fsync(fd_tmp)
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


def clear_autonomous_record(session_id: str) -> bool:
    """Remove the autonomous-mode record for ``session_id``.

    Returns whether the record is GONE when this returns -- which is what
    the caller needs to know, not whether ``unlink`` was reached. An invalid
    session id yields ``False``: nothing was cleared, and the caller must
    not report otherwise. An already-absent record yields ``True``, so the
    call stays idempotent.

    This is the escape hatch's only mechanism. It reports the ARTIFACT (the
    record is absent), not the call, because a clear that silently failed
    while the confirmation still printed would tell the operator their only
    exit from a blocking Stop hook had worked when the hook goes on
    refusing every turn-end. Never raises: a filesystem fault is reported as
    ``False``, and the caller says so.
    """
    path = _record_path(session_id)
    if path is None:
        return False
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        return not path.exists()
    except OSError:
        return False


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


@contextmanager
def _record_lock(session_id: str) -> Iterator[bool]:
    """Hold an exclusive lock over one session's read-modify-write, if possible.

    Every hook event is a SEPARATE PROCESS, so ``record_blocked_stop`` and
    ``append_decision`` are genuinely concurrent, and their unlocked
    read-modify-write drops whichever update lands second. The dropped one
    can be a valve timestamp -- and the valve is the only thing bounding the
    block loop now that the harness cap is disabled, so a lost update
    degrades the escape from the loop, not merely the bookkeeping. That is
    why this is locked and the operator-initiated ``write_autonomous_record``
    is not: that one is a whole-record write with no read to lose.

    Yields whether the lock is actually held. Failing to take it does NOT
    skip the update: the caller proceeds unlocked, which is exactly the
    behaviour without this function, so the lock can only narrow the race
    and never widen it. Both failure modes are why -- an unwritable state
    directory cannot create a lock file (and the update's own write is about
    to fail on its own terms, which the caller already handles), and a
    contended lock must not turn one dropped update into a hook that
    refuses to record anything at all.
    """
    lock_path = _autonomous_dir() / f"{session_id}.lock"
    lock = CrossPlatformLock(lock_path, blocking=True)
    held = False
    try:
        try:
            held = lock.acquire()
        except OSError:
            held = False
        yield held
    finally:
        if held:
            try:
                lock.release()
            except OSError:
                pass


def recent_block_times(record: Any) -> list[float]:
    """The recorded block timestamps in ``record``, oldest first.

    An absent, null, or non-list value yields an empty list. Never raises.
    """
    if not isinstance(record, dict):
        return []
    stamps = record.get("block_times")
    if not isinstance(stamps, list):
        return []
    out: list[float] = []
    for s in stamps:
        if isinstance(s, bool) or not isinstance(s, (int, float)):
            continue
        # ``record`` is typed ``Any``: callers may hand this an unvalidated
        # dict, so the int too large to become a float is dropped here as
        # well as rejected in ``_validate_record``. Dropping rather than
        # raising keeps the documented contract on the only path where a
        # raise would reach the Stop hook.
        try:
            out.append(float(s))
        except (OverflowError, ValueError):
            continue
    return out


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
    nth_most_recent = sorted(stamps)[-BLOCK_WINDOW_LIMIT]
    return (now - nth_most_recent) <= BLOCK_WINDOW_SECONDS


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

    ``None`` obliges the Stop hook to ALLOW the stop it was about to refuse.
    The valve opens on RECORDED blocks, so a block that could not be
    recorded can never contribute to opening it: issue one anyway and the
    session is refused forever with nothing accumulating to release it. A
    block that cannot be accounted for must not be issued.
    """
    with _record_lock(session_id):
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
            set_at=record["set_at"],
            blocked_stops=new_count,
            decisions=record["decisions"],
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
    with _record_lock(session_id):
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
            set_at=record["set_at"],
            blocked_stops=record["blocked_stops"],
            decisions=new_decisions,
            block_times=record.get("block_times"),
        )
    return bool(ok)
