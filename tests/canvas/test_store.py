"""Tests for ``spellbook.canvas.store``.

Covers: name regex, canvas root resolution, atomic page write, atomic meta
write, full canvas read (happy + missing-meta regeneration), and path-
traversal rejection.
"""

from __future__ import annotations

import json
import os

import pytest
import tripwire
from dirty_equals import IsInstance

from spellbook.canvas import store


def test_resolve_canvas_root(canvas_tmp_root):
    """Monkeypatched ``_resolve_canvas_root`` returns the patched path."""
    assert store._resolve_canvas_root() == canvas_tmp_root


@pytest.mark.parametrize(
    "name",
    [
        "foo",
        "foo-bar",
        "foo_bar_1",
        "a",
        "a" * 64,
        "0abc",
        "1",
    ],
)
def test_name_regex_valid(name):
    assert store.NAME_RE.match(name) is not None


@pytest.mark.parametrize(
    "name",
    [
        "",
        "-foo",
        "_foo",
        "FOO",
        "Foo",
        "foo/bar",
        "foo bar",
        "a" * 65,
        "..",
        "../etc",
        ".hidden",
    ],
)
def test_name_regex_invalid(name):
    assert store.NAME_RE.match(name) is None


def test_atomic_write_page_happy(canvas_tmp_root):
    """``write_page`` produces ``pages/index.md`` with exact content."""
    store.open_canvas("foo")
    n = store.write_page("foo", "hello world")
    page_path = os.path.join(canvas_tmp_root, "foo", "pages", "index.md")
    assert os.path.isfile(page_path)
    with open(page_path, "r", encoding="utf-8") as f:
        assert f.read() == "hello world"
    assert n == len(b"hello world")


def test_atomic_write_page_partial_recovery(canvas_tmp_root, monkeypatch):
    """If ``os.replace`` fails mid-write, no partial file remains.

    The tempfile pattern guarantees: either the final path holds the new
    bytes, or it holds the old bytes (here: empty). No half-written file
    is visible at the final path; the tmp file is cleaned up.
    """
    store.open_canvas("foo")
    # Initial state: empty index.md from open_canvas
    page_path = os.path.join(canvas_tmp_root, "foo", "pages", "index.md")
    assert os.path.isfile(page_path)
    original_replace = os.replace

    def boom(src, dst):
        raise OSError("simulated rename failure")

    monkeypatch.setattr("spellbook.canvas.store.os.replace", boom)

    with pytest.raises(OSError, match="simulated rename failure"):
        store.write_page("foo", "new content")

    # The original (empty) page is intact; no .tmp- files left behind.
    with open(page_path, "r", encoding="utf-8") as f:
        assert f.read() == ""
    leftover_tmp = [
        n
        for n in os.listdir(os.path.dirname(page_path))
        if n.startswith(".tmp-")
    ]
    assert leftover_tmp == [], f"Stray tmp files: {leftover_tmp}"
    # Restore for cleanup
    monkeypatch.setattr("spellbook.canvas.store.os.replace", original_replace)


def test_atomic_write_meta(canvas_tmp_root):
    """``write_meta`` produces ``meta.json`` parsable back into ``CanvasMeta``."""
    meta, _, _ = store.open_canvas("foo", title="Foo Title")
    meta_path = os.path.join(canvas_tmp_root, "foo", "meta.json")
    assert os.path.isfile(meta_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        parsed = json.load(f)
    assert parsed["name"] == "foo"
    assert parsed["title"] == "Foo Title"
    assert parsed["closed"] is False
    assert parsed["schema_version"] == 2  # bumped 1->2 (decision-capable, §3.2)
    assert parsed["decision"] is None  # additive field serialized as null
    # Round-trip
    back = store.CanvasMeta.model_validate(parsed)
    assert back.name == "foo"
    assert back.title == "Foo Title"


def test_read_canvas_happy(canvas_tmp_root):
    """``read_canvas`` returns the full content dict for a populated canvas."""
    store.open_canvas("bar", title="Bar")
    store.write_page("bar", "# hello")
    result = store.read_canvas("bar")
    assert result is not None
    # Full-dict equality. ``created_at``/``last_updated`` are the only dynamic
    # fields (server clock at open); anchor them to the actual values so every
    # other field — including ``decision`` being None — is verified exactly,
    # with no extra or missing keys (cf. test_submit_happy_path's full-equality
    # pattern with an anchored dynamic field).
    assert result == {
        "name": "bar",
        "title": "Bar",
        "created_at": result["created_at"],
        "last_updated": result["last_updated"],
        "closed": False,
        "page": "index.md",
        "content": "# hello",
        "bytes": len(b"# hello"),
        "decision": None,
    }


def test_read_canvas_missing_meta_regenerates(canvas_tmp_root):
    """If ``meta.json`` is missing, ``read_canvas`` regenerates it with defaults."""
    canvas_dir = os.path.join(canvas_tmp_root, "baz")
    os.makedirs(os.path.join(canvas_dir, "pages"))
    page_path = os.path.join(canvas_dir, "pages", "index.md")
    with open(page_path, "w", encoding="utf-8") as f:
        f.write("orphaned content")

    result = store.read_canvas("baz")
    assert result is not None
    assert result["name"] == "baz"
    assert result["title"] == "baz"  # defaulted to name
    assert result["content"] == "orphaned content"
    assert result["closed"] is False
    # meta.json should now exist
    assert os.path.isfile(os.path.join(canvas_dir, "meta.json"))


def test_read_canvas_path_traversal_rejected(canvas_tmp_root):
    """``read_canvas('../etc/passwd')`` returns ``None`` before any FS access."""
    result = store.read_canvas("../etc/passwd")
    assert result is None


def test_read_canvas_missing_dir_returns_none(canvas_tmp_root):
    assert store.read_canvas("does-not-exist") is None


def test_open_canvas_idempotent(canvas_tmp_root):
    """Calling ``open_canvas`` twice on the same name does not duplicate state."""
    meta1, created1, reopened1 = store.open_canvas("foo")
    meta2, created2, reopened2 = store.open_canvas("foo")
    assert created1 is True and reopened1 is False
    assert created2 is False and reopened2 is False
    assert meta1.created_at == meta2.created_at


def test_open_canvas_reopens_closed(canvas_tmp_root):
    store.open_canvas("foo")
    store.close_canvas("foo")
    meta, created, reopened = store.open_canvas("foo")
    assert created is False
    assert reopened is True
    assert meta.closed is False


def test_open_canvas_invalid_name(canvas_tmp_root):
    with pytest.raises(ValueError):
        store.open_canvas("../etc")


def test_list_canvases_empty(canvas_tmp_root):
    assert store.list_canvases() == []


def test_list_canvases_sorted_by_last_updated_desc(canvas_tmp_root):
    """Newer ``last_updated`` comes first.

    ``write_page`` is page-only; ``canvas_write`` (MCP layer, A.3) bumps
    ``meta.last_updated``. Here we simulate the MCP layer by writing
    explicit ``last_updated`` timestamps directly, so the assertion does
    not rely on wall-clock spacing between ``open_canvas`` calls (slow
    CI can produce identical timestamps within a millisecond resolution
    grid).
    """
    from datetime import datetime, timedelta, timezone

    meta_alpha, _, _ = store.open_canvas("alpha")
    meta_beta, _, _ = store.open_canvas("beta")
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    # beta is older; alpha is bumped to be newer.
    store.write_meta(
        "beta", meta_beta.model_copy(update={"last_updated": base})
    )
    store.write_meta(
        "alpha",
        meta_alpha.model_copy(update={"last_updated": base + timedelta(seconds=1)}),
    )
    items = store.list_canvases()
    names = [i["name"] for i in items]
    assert names == ["alpha", "beta"]


def test_close_canvas(canvas_tmp_root):
    store.open_canvas("foo")
    closed_meta = store.close_canvas("foo")
    assert closed_meta is not None
    assert closed_meta.closed is True


def test_close_canvas_not_found(canvas_tmp_root):
    assert store.close_canvas("nope") is None


def test_write_page_invalid_name(canvas_tmp_root):
    with pytest.raises(ValueError):
        store.write_page("../etc", "x")


def test_write_page_oversize(canvas_tmp_root, monkeypatch):
    """``write_page`` honours ``_max_page_bytes`` read at call time."""
    monkeypatch.setenv("SPELLBOOK_CANVAS_MAX_PAGE_BYTES", "10")
    store.open_canvas("foo")
    with pytest.raises(ValueError, match="page_too_large"):
        store.write_page("foo", "0123456789X")  # 11 bytes


def test_max_page_bytes_non_integer_falls_back_to_default(monkeypatch, caplog):
    """Malformed env var is logged and ignored, not raised."""
    monkeypatch.setenv("SPELLBOOK_CANVAS_MAX_PAGE_BYTES", "not-an-int")
    with caplog.at_level("WARNING"):
        result = store._max_page_bytes()
    assert result == 1 * 1024 * 1024
    assert any("not-an-int" in r.message for r in caplog.records)


def test_max_page_bytes_non_positive_falls_back_to_default(monkeypatch, caplog):
    """Zero or negative env var is logged and ignored."""
    monkeypatch.setenv("SPELLBOOK_CANVAS_MAX_PAGE_BYTES", "0")
    with caplog.at_level("WARNING"):
        result = store._max_page_bytes()
    assert result == 1 * 1024 * 1024
    assert any("must be positive" in r.message for r in caplog.records)


def test_max_page_bytes_unset_returns_default(monkeypatch):
    """Unset env var returns the 1 MB default."""
    monkeypatch.delenv("SPELLBOOK_CANVAS_MAX_PAGE_BYTES", raising=False)
    assert store._max_page_bytes() == 1 * 1024 * 1024


def test_write_page_non_index(canvas_tmp_root):
    """MVP only accepts ``index.md``."""
    store.open_canvas("foo")
    with pytest.raises(ValueError, match="invalid_content"):
        store.write_page("foo", "x", page="other.md")


def test_read_canvas_corrupt_meta_regenerated(canvas_tmp_root):
    """Corrupt ``meta.json`` is replaced with a default-derived value."""
    store.open_canvas("foo")
    canvas_dir = os.path.join(canvas_tmp_root, "foo")
    with open(os.path.join(canvas_dir, "meta.json"), "w") as f:
        f.write("not json {")
    result = store.read_canvas("foo")
    assert result is not None
    assert result["name"] == "foo"
    assert result["title"] == "foo"


def test_list_canvases_skips_non_dirs_and_invalid_names(canvas_tmp_root):
    """Files at the root and badly-named subdirs are ignored."""
    store.open_canvas("good")
    # Stray file
    with open(os.path.join(canvas_tmp_root, "stray.txt"), "w") as f:
        f.write("noise")
    # Bad-name directory
    os.makedirs(os.path.join(canvas_tmp_root, "BadName"))
    items = store.list_canvases()
    assert [i["name"] for i in items] == ["good"]


def test_list_canvases_regenerates_missing_meta(canvas_tmp_root):
    """Directories with no meta.json get a synthesized entry."""
    canvas_dir = os.path.join(canvas_tmp_root, "orphan")
    os.makedirs(os.path.join(canvas_dir, "pages"))
    with open(os.path.join(canvas_dir, "pages", "index.md"), "w") as f:
        f.write("x")
    items = store.list_canvases()
    names = [i["name"] for i in items]
    assert "orphan" in names
    # meta.json should now be on disk.
    assert os.path.isfile(os.path.join(canvas_dir, "meta.json"))


def test_list_canvases_root_missing(monkeypatch, tmp_path):
    """When the canvas root doesn't exist, list returns []."""
    monkeypatch.setattr(
        "spellbook.canvas.store._resolve_canvas_root",
        lambda: str(tmp_path / "no-such-dir"),
    )
    assert store.list_canvases() == []


def test_close_canvas_invalid_name(canvas_tmp_root):
    assert store.close_canvas("../etc") is None


def test_close_canvas_corrupt_meta(canvas_tmp_root):
    """``close_canvas`` on corrupt meta returns ``None``."""
    store.open_canvas("foo")
    canvas_dir = os.path.join(canvas_tmp_root, "foo")
    with open(os.path.join(canvas_dir, "meta.json"), "w") as f:
        f.write("garbage")
    assert store.close_canvas("foo") is None


def test_open_canvas_with_corrupt_meta_treated_as_regenerate(canvas_tmp_root):
    """Existing dir + corrupt meta: open_canvas regenerates and reports created=False."""
    store.open_canvas("foo")
    canvas_dir = os.path.join(canvas_tmp_root, "foo")
    with open(os.path.join(canvas_dir, "meta.json"), "w") as f:
        f.write("garbage")
    meta, created, reopened = store.open_canvas("foo")
    assert created is False
    assert reopened is False
    assert meta.title == "foo"


def test_default_canvas_root_is_under_home():
    """The unmonkeypatched root points under the user's home dir."""
    import os.path
    root = store._resolve_canvas_root()
    assert root.endswith(os.path.join(".local", "spellbook", "canvas"))


# ---------------------------------------------------------------------------
# Task A1: decision_contract module + CanvasMeta.decision + compat
# ---------------------------------------------------------------------------

from datetime import datetime, timezone

from spellbook.canvas.decision_contract import (
    DecisionCode,
    SUBMISSION_SCHEMA_VERSION,
    validate_submission_value,
    project_decision_for_detail,
)
from spellbook.canvas.store import (
    CanvasMeta,
    DecisionOption,
    PendingDecision,
    AwaitBinding,
)


def test_submission_schema_version_is_one():
    assert SUBMISSION_SCHEMA_VERSION == 1


def test_decision_code_values_exact():
    # Closed vocabulary; wire strings are load-bearing (RT-4).
    assert DecisionCode.ACCEPTED.value == "accepted"
    assert DecisionCode.ALREADY_DECIDED.value == "already_decided"
    assert DecisionCode.NO_SUCH_DECISION.value == "no_such_decision"
    assert DecisionCode.BINDING_MISMATCH.value == "binding_mismatch"
    assert DecisionCode.INVALID_VALUE.value == "invalid_value"
    assert DecisionCode.CANVAS_CLOSED.value == "canvas_closed"
    assert DecisionCode.CANCELLED.value == "cancelled"
    assert DecisionCode.DECISION_EXISTS.value == "decision_exists"
    assert DecisionCode.NO_SESSION_IDENTITY.value == "no_session_identity"
    assert DecisionCode.SCHEMA_UNSUPPORTED.value == "schema_unsupported"
    assert DecisionCode.INVALID_NAME.value == "invalid_name"
    assert DecisionCode.INVALID_DECISION_ID.value == "invalid_decision_id"
    assert DecisionCode.INVALID_KIND.value == "invalid_kind"
    assert DecisionCode.INVALID_OPTIONS.value == "invalid_options"
    assert DecisionCode.NOT_FOUND.value == "not_found"


def _binding():
    return AwaitBinding(session_id="abc123", await_token="tok-xyz")


def _choice_decision():
    return PendingDecision(
        decision_id="approve-design",
        kind="choice",
        prompt="Pick a path",
        options=[
            DecisionOption(value="a", label="Option A"),
            DecisionOption(value="b", label="Option B"),
        ],
        await_binding=_binding(),
        status="pending",
        created_at=datetime(2026, 6, 4, tzinfo=timezone.utc),
    )


def test_validate_submission_value_choice():
    d = _choice_decision()
    assert validate_submission_value(d, "a") is True
    assert validate_submission_value(d, "b") is True
    assert validate_submission_value(d, "c") is False


def test_validate_submission_value_approve():
    d = PendingDecision(
        decision_id="ship-it",
        kind="approve",
        prompt="Ship?",
        options=None,
        await_binding=_binding(),
        status="pending",
        created_at=datetime(2026, 6, 4, tzinfo=timezone.utc),
    )
    assert validate_submission_value(d, "approved") is True
    assert validate_submission_value(d, "declined") is True
    assert validate_submission_value(d, "maybe") is False


def test_project_decision_for_detail_strips_binding():
    d = _choice_decision()
    projected = project_decision_for_detail(d)
    assert projected == {
        "decision_id": "approve-design",
        "kind": "choice",
        "prompt": "Pick a path",
        "options": [
            {"value": "a", "label": "Option A"},
            {"value": "b", "label": "Option B"},
        ],
        "status": "pending",
    }
    # await_binding never leaves the daemon (DA-2)
    assert "await_binding" not in projected


def test_project_decision_for_detail_none():
    assert project_decision_for_detail(None) is None


def test_canvas_meta_decision_defaults_none():
    meta = CanvasMeta(
        name="plan-x",
        title="Plan X",
        created_at=datetime(2026, 6, 4, tzinfo=timezone.utc),
        last_updated=datetime(2026, 6, 4, tzinfo=timezone.utc),
    )
    assert meta.decision is None
    assert meta.schema_version == 2


def test_v1_meta_json_loads_with_decision_none(canvas_tmp_root):
    # Migration-free compat (§13): a v1 meta.json (no decision, schema_version 1)
    # validates with decision=None.
    store.open_canvas("legacy", title="Legacy")
    canvas_dir = os.path.join(store._resolve_canvas_root(), "legacy")
    v1_payload = {
        "name": "legacy",
        "title": "Legacy",
        "created_at": "2026-06-04T00:00:00+00:00",
        "last_updated": "2026-06-04T00:00:00+00:00",
        "closed": False,
        "schema_version": 1,
    }
    with open(os.path.join(canvas_dir, "meta.json"), "w") as fh:
        json.dump(v1_payload, fh)
    meta = store.read_meta("legacy")
    assert meta is not None
    assert meta.decision is None


# ---------------------------------------------------------------------------
# Task A2: declare_decision store function
# ---------------------------------------------------------------------------


def test_declare_decision_writes_meta(canvas_tmp_root):
    store.open_canvas("plan-x", title="Plan X")
    result = store.declare_decision(
        name="plan-x",
        decision_id="d1",
        kind="choice",
        prompt="Pick",
        options=[{"value": "a", "label": "A"}, {"value": "b", "label": "B"}],
        session_id="sess-1",
        await_token="tok-1",
    )
    assert result == DecisionCode.ACCEPTED
    meta = store.read_meta("plan-x")
    assert meta.decision is not None
    assert meta.decision.decision_id == "d1"
    assert meta.decision.kind == "choice"
    assert meta.decision.status == "pending"
    assert meta.decision.await_binding.session_id == "sess-1"
    assert meta.decision.await_binding.await_token == "tok-1"


def test_declare_decision_rejects_existing(canvas_tmp_root):
    store.open_canvas("plan-x", title="Plan X")
    store.declare_decision("plan-x", "d1", "approve", "Ship?", None, "s", "t")
    second = store.declare_decision("plan-x", "d2", "approve", "Again?", None, "s", "t")
    assert second == DecisionCode.DECISION_EXISTS


def test_declare_decision_rejects_closed(canvas_tmp_root):
    store.open_canvas("plan-x", title="Plan X")
    store.close_canvas("plan-x")
    result = store.declare_decision("plan-x", "d1", "approve", "Ship?", None, "s", "t")
    assert result == DecisionCode.CANVAS_CLOSED


def test_declare_decision_invalid_options_over_limit(canvas_tmp_root):
    store.open_canvas("plan-x", title="Plan X")
    opts = [{"value": f"v{i}", "label": f"L{i}"} for i in range(21)]
    result = store.declare_decision("plan-x", "d1", "choice", "Pick", opts, "s", "t")
    assert result == DecisionCode.INVALID_OPTIONS


def test_declare_decision_invalid_kind(canvas_tmp_root):
    store.open_canvas("plan-x", title="Plan X")
    result = store.declare_decision("plan-x", "d1", "freeform", "Q", None, "s", "t")
    assert result == DecisionCode.INVALID_KIND


# ---------------------------------------------------------------------------
# Gemini round-5 F1: malformed option STRUCTURE must return INVALID_OPTIONS,
# never crash. The pre-fix validation called opt.get(...) and len(value/label)
# directly, so a non-dict option (AttributeError) or a non-str value/label
# (TypeError) escaped the closed DecisionCode vocabulary and crashed the
# store/MCP-tool layer instead of returning a clean INVALID_OPTIONS. The
# decision was NOT written in any of these cases (no partial meta).
# ---------------------------------------------------------------------------


def test_declare_decision_invalid_options_non_dict_element(canvas_tmp_root):
    """A non-dict option element (e.g. a bare string) returns INVALID_OPTIONS,
    not AttributeError, and writes no decision."""
    store.open_canvas("plan-x", title="Plan X")
    result = store.declare_decision(
        "plan-x", "d1", "choice", "Pick", ["notadict"], "s", "t"
    )
    assert result == DecisionCode.INVALID_OPTIONS
    assert store.read_meta("plan-x").decision is None


def test_declare_decision_invalid_options_none_value(canvas_tmp_root):
    """An option whose value is None returns INVALID_OPTIONS, not TypeError,
    and writes no decision."""
    store.open_canvas("plan-x", title="Plan X")
    result = store.declare_decision(
        "plan-x", "d1", "choice", "Pick", [{"value": None, "label": "x"}], "s", "t"
    )
    assert result == DecisionCode.INVALID_OPTIONS
    assert store.read_meta("plan-x").decision is None


def test_declare_decision_invalid_options_non_str_value_and_label(canvas_tmp_root):
    """An option with int value/label returns INVALID_OPTIONS, not TypeError,
    and writes no decision."""
    store.open_canvas("plan-x", title="Plan X")
    result = store.declare_decision(
        "plan-x", "d1", "choice", "Pick", [{"value": 1, "label": 2}], "s", "t"
    )
    assert result == DecisionCode.INVALID_OPTIONS
    assert store.read_meta("plan-x").decision is None


def test_declare_decision_invalid_options_missing_keys(canvas_tmp_root):
    """An option missing the value/label keys returns INVALID_OPTIONS (an
    empty-valued choice option can never be submitted against), and writes no
    decision."""
    store.open_canvas("plan-x", title="Plan X")
    result = store.declare_decision(
        "plan-x", "d1", "choice", "Pick", [{}], "s", "t"
    )
    assert result == DecisionCode.INVALID_OPTIONS
    assert store.read_meta("plan-x").decision is None


# ---------------------------------------------------------------------------
# Task A3: claim_submission (O_EXCL first-wins) + value validation
# ---------------------------------------------------------------------------

import threading


def _seed_decision(name, did, kind="choice", opts=("a", "b")):
    store.open_canvas(name, title=name)
    options = (
        [{"value": o, "label": o.upper()} for o in opts] if kind == "choice" else None
    )
    store.declare_decision(name, did, kind, "Q", options, "sess-1", "tok-1")


def _item(name, did, value, kind="choice"):
    return {
        "schema_version": SUBMISSION_SCHEMA_VERSION,
        "decision_id": did,
        "canvas": name,
        "kind": kind,
        "value": value,
        "free_text": None,
        "await_binding": {"session_id": "sess-1", "await_token": "tok-1"},
        "submitted_at": "2026-06-04T18:22:01.001Z",
        "consumed": False,
    }


def test_claim_submission_first_wins(canvas_tmp_root):
    _seed_decision("plan-x", "d1")
    first = store.claim_submission("plan-x", "d1", _item("plan-x", "d1", "a"))
    assert first == DecisionCode.ACCEPTED
    second = store.claim_submission("plan-x", "d1", _item("plan-x", "d1", "b"))
    assert second == DecisionCode.ALREADY_DECIDED
    inbox = os.path.join(store._resolve_canvas_root(), "plan-x", "inbox", "d1.json")
    assert os.path.getsize(inbox) > 0  # fsync durability: non-empty winner


def test_claim_submission_writes_complete_payload(canvas_tmp_root):
    # The winner's inbox file must contain the COMPLETE json.dumps(item) payload,
    # byte-for-byte -- not a truncated/short-written prefix. Uses a free_text
    # field large enough that a single os.write syscall could short-write, which
    # is exactly the footgun the os.fdopen(fd, "wb") wrapper guards against.
    _seed_decision("plan-x", "d1")
    item = _item("plan-x", "d1", "a")
    item["free_text"] = "Z" * (1024 * 1024)  # 1 MiB: large enough to risk a short write
    result = store.claim_submission("plan-x", "d1", item)
    assert result == DecisionCode.ACCEPTED
    inbox = os.path.join(store._resolve_canvas_root(), "plan-x", "inbox", "d1.json")
    expected = json.dumps(item).encode("utf-8")
    with open(inbox, "rb") as fh:
        assert fh.read() == expected  # full payload landed, every byte


def test_claim_submission_invalid_value(canvas_tmp_root):
    _seed_decision("plan-x", "d1")
    result = store.claim_submission("plan-x", "d1", _item("plan-x", "d1", "zzz"))
    assert result == DecisionCode.INVALID_VALUE
    inbox = os.path.join(store._resolve_canvas_root(), "plan-x", "inbox", "d1.json")
    assert os.path.exists(inbox) is False  # invalid value never lands a file


def test_claim_submission_closed(canvas_tmp_root):
    # I5: store-level RED for the §5.2 409 canvas_closed row (route maps it).
    _seed_decision("plan-x", "d1")
    store.close_canvas("plan-x")
    result = store.claim_submission("plan-x", "d1", _item("plan-x", "d1", "a"))
    assert result == DecisionCode.CANVAS_CLOSED
    inbox = os.path.join(store._resolve_canvas_root(), "plan-x", "inbox", "d1.json")
    assert os.path.exists(inbox) is False  # closed never lands a file


def test_claim_submission_cancelled(canvas_tmp_root):
    # I5: store-level RED for the §5.2 409 cancelled row.
    _seed_decision("plan-x", "d1")
    store.cancel_decision("plan-x", "d1")
    result = store.claim_submission("plan-x", "d1", _item("plan-x", "d1", "a"))
    assert result == DecisionCode.CANCELLED
    inbox = os.path.join(store._resolve_canvas_root(), "plan-x", "inbox", "d1.json")
    assert os.path.exists(inbox) is False  # cancelled never lands a file


def test_claim_submission_binding_mismatch(canvas_tmp_root):
    # I5 / DA-2: an item whose await_binding does not match the stored decision
    # binding is rejected with BINDING_MISMATCH and lands no file. The seeded
    # decision binds session_id="sess-1"/await_token="tok-1"; supply a wrong token.
    _seed_decision("plan-x", "d1")
    item = _item("plan-x", "d1", "a")
    item["await_binding"] = {"session_id": "sess-1", "await_token": "WRONG"}
    result = store.claim_submission("plan-x", "d1", item)
    assert result == DecisionCode.BINDING_MISMATCH
    inbox = os.path.join(store._resolve_canvas_root(), "plan-x", "inbox", "d1.json")
    assert os.path.exists(inbox) is False  # binding mismatch never lands a file


def test_claim_submission_barrier_race(canvas_tmp_root):
    _seed_decision("plan-x", "d1")
    barrier = threading.Barrier(2)
    results = {}

    def claim(tag, value):
        barrier.wait()  # release both into O_EXCL simultaneously
        results[tag] = store.claim_submission("plan-x", "d1", _item("plan-x", "d1", value))

    t1 = threading.Thread(target=claim, args=("t1", "a"))
    t2 = threading.Thread(target=claim, args=("t2", "b"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    outcomes = sorted([results["t1"], results["t2"]], key=lambda c: c.value)
    assert outcomes == [DecisionCode.ACCEPTED, DecisionCode.ALREADY_DECIDED]


# ---------------------------------------------------------------------------
# Task A4: claim_consume + cancel_decision + peek_decision
# ---------------------------------------------------------------------------


def test_consume_decision_code_values_exact():
    assert DecisionCode.CONSUMED_NOW.value == "consumed_now"
    assert DecisionCode.ALREADY_CONSUMED.value == "already_consumed"
    assert DecisionCode.NO_SUBMISSION.value == "no_submission"


def _land_submission(name, did, value="a"):
    _seed_decision(name, did)
    assert store.claim_submission(name, did, _item(name, did, value)) == DecisionCode.ACCEPTED


def test_claim_consume_first_consumer_wins(canvas_tmp_root):
    _land_submission("plan-x", "d1")
    r1 = store.claim_consume("plan-x", "d1")
    assert r1.result == DecisionCode.CONSUMED_NOW
    assert r1.payload["value"] == "a"
    r2 = store.claim_consume("plan-x", "d1")
    assert r2.result == DecisionCode.ALREADY_CONSUMED
    assert r2.payload is None
    # file persists (never deleted) — mark-consumed-never-delete
    inbox = os.path.join(store._resolve_canvas_root(), "plan-x", "inbox", "d1.json")
    assert os.path.exists(inbox) is True


def test_claim_consume_barrier_exactly_once(canvas_tmp_root):
    _land_submission("plan-x", "d1")
    barrier = threading.Barrier(2)
    results = {}

    def consume(tag):
        barrier.wait()
        results[tag] = store.claim_consume("plan-x", "d1")

    t1 = threading.Thread(target=consume, args=("t1",))
    t2 = threading.Thread(target=consume, args=("t2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    codes = sorted([results["t1"].result, results["t2"].result], key=lambda c: c.value)
    assert codes == [DecisionCode.ALREADY_CONSUMED, DecisionCode.CONSUMED_NOW]
    payloads = [r.payload for r in (results["t1"], results["t2"]) if r.payload is not None]
    assert len(payloads) == 1  # delivered exactly once


def test_claim_consume_no_submission(canvas_tmp_root):
    _seed_decision("plan-x", "d1")
    r = store.claim_consume("plan-x", "d1")
    assert r.result == DecisionCode.NO_SUBMISSION


def test_cancel_decision_idempotent(canvas_tmp_root):
    _seed_decision("plan-x", "d1")
    assert store.cancel_decision("plan-x", "d1") == DecisionCode.CANCELLED
    meta = store.read_meta("plan-x")
    assert meta.decision.status == "cancelled"
    assert store.cancel_decision("plan-x", "d1") == DecisionCode.CANCELLED  # idempotent


def test_peek_decision_non_consuming(canvas_tmp_root):
    _land_submission("plan-x", "d1")
    before = store.peek_decision("plan-x", "d1")
    assert before == {"status": "submitted", "kind": "choice"}
    after = store.peek_decision("plan-x", "d1")
    assert after == {"status": "submitted", "kind": "choice"}  # never flips
    consumed = os.path.join(store._resolve_canvas_root(), "plan-x", "inbox", "d1.consumed")
    assert os.path.exists(consumed) is False


def test_peek_decision_none(canvas_tmp_root):
    store.open_canvas("empty", title="Empty")
    assert store.peek_decision("empty", "nope") == {"status": "none"}


# ---------------------------------------------------------------------------
# Task A5: read_canvas projects the decision field
# ---------------------------------------------------------------------------


def test_read_canvas_includes_projected_decision(canvas_tmp_root):
    _seed_decision("plan-x", "d1")
    result = store.read_canvas("plan-x")
    assert result["decision"] == {
        "decision_id": "d1",
        "kind": "choice",
        "prompt": "Q",
        "options": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}],
        "status": "pending",
    }
    assert "await_binding" not in result["decision"]


def test_read_canvas_decision_none_when_absent(canvas_tmp_root):
    store.open_canvas("plain", title="Plain")
    result = store.read_canvas("plain")
    assert result["decision"] is None


# ---------------------------------------------------------------------------
# Code-review F1: corrupt inbox JSON must not burn the .consumed marker
# ---------------------------------------------------------------------------


def test_corrupt_submission_decision_code_value_exact():
    # New wire string is load-bearing (RT-4): the SPA / agent see it verbatim.
    assert DecisionCode.CORRUPT_SUBMISSION.value == "corrupt_submission"


def _corrupt_inbox(name, did):
    """Land a submission, then overwrite its inbox JSON with garbage bytes."""
    _land_submission(name, did)
    inbox = os.path.join(store._resolve_canvas_root(), name, "inbox", f"{did}.json")
    with open(inbox, "wb") as fh:
        fh.write(b"{not valid json at all")
    return inbox


def test_claim_consume_corrupt_json_returns_corrupt_no_marker(canvas_tmp_root):
    """Corrupt inbox JSON yields CORRUPT_SUBMISSION, no payload, and the
    ``.consumed`` marker is NOT created (so the payload stays recoverable)."""
    inbox = _corrupt_inbox("plan-x", "d1")
    result = store.claim_consume("plan-x", "d1")
    assert result == store.ConsumeResult(DecisionCode.CORRUPT_SUBMISSION, None)
    marker = os.path.join(
        store._resolve_canvas_root(), "plan-x", "inbox", "d1.consumed"
    )
    assert os.path.exists(marker) is False  # marker must NOT be burned
    # The corrupt inbox file is left in place for repair (never deleted).
    assert os.path.exists(inbox) is True


def test_claim_consume_recoverable_after_repair(canvas_tmp_root):
    """After a corrupt read returns CORRUPT_SUBMISSION (no marker burned),
    repairing the inbox file makes the payload deliverable exactly once."""
    inbox = _corrupt_inbox("plan-x", "d1")
    first = store.claim_consume("plan-x", "d1")
    assert first == store.ConsumeResult(DecisionCode.CORRUPT_SUBMISSION, None)
    # Repair: write back a valid submission item.
    good_item = _item("plan-x", "d1", "a")
    with open(inbox, "w", encoding="utf-8") as fh:
        json.dump(good_item, fh)
    repaired = store.claim_consume("plan-x", "d1")
    assert repaired == store.ConsumeResult(DecisionCode.CONSUMED_NOW, good_item)
    # Second consume after a successful one is ALREADY_CONSUMED (marker now set).
    again = store.claim_consume("plan-x", "d1")
    assert again == store.ConsumeResult(DecisionCode.ALREADY_CONSUMED, None)


# ---------------------------------------------------------------------------
# Code-review F2: decision-status writes must merge, not clobber concurrent
# meta updates (re-read meta immediately before write)
# ---------------------------------------------------------------------------


def test_claim_submission_preserves_concurrent_meta_field(canvas_tmp_root):
    """A concurrent ``last_updated``/``title`` bump landing between
    ``claim_submission``'s initial read and its decision-status write must
    survive. Interleaving is forced deterministically via the merge seam
    hook (no sleeps)."""
    _seed_decision("plan-x", "d1")
    concurrent_ts = datetime(2030, 1, 1, tzinfo=timezone.utc)

    def interleave(name):
        # Simulate a concurrent canvas_write: bump title + last_updated on the
        # freshest meta on disk, between the claim's read and its merge-write.
        current = store.read_meta(name)
        store.write_meta(
            name,
            current.model_copy(
                update={"title": "Concurrently Renamed", "last_updated": concurrent_ts}
            ),
        )

    store._set_decision_merge_hook(interleave)
    try:
        result = store.claim_submission("plan-x", "d1", _item("plan-x", "d1", "a"))
    finally:
        store._set_decision_merge_hook(None)

    assert result == DecisionCode.ACCEPTED
    meta = store.read_meta("plan-x")
    # The concurrent title + timestamp survive (merge, not clobber)...
    assert meta.title == "Concurrently Renamed"
    assert meta.last_updated == concurrent_ts
    # ...AND the decision-status flip the claim performed is applied.
    assert meta.decision.status == "submitted"
    assert meta.decision.decision_id == "d1"


def test_cancel_then_submit_interleave_last_writer_wins(canvas_tmp_root):
    """cancel-vs-submit interleave: the LAST atomic decision write wins per
    the merge rule. Here a cancel lands between submit's read and merge-write;
    submit re-reads, sees cancelled, and must not resurrect 'submitted'."""
    _seed_decision("plan-x", "d1")

    def interleave(name):
        # A cancel races in after claim_submission read the (pending) decision.
        assert store.cancel_decision(name, "d1") == DecisionCode.CANCELLED

    store._set_decision_merge_hook(interleave)
    try:
        result = store.claim_submission("plan-x", "d1", _item("plan-x", "d1", "a"))
    finally:
        store._set_decision_merge_hook(None)

    # The inbox file still landed (O_EXCL won before the merge), but the
    # status reflects the LAST atomic winner: cancelled, not submitted.
    assert result == DecisionCode.ACCEPTED
    meta = store.read_meta("plan-x")
    assert meta.decision.status == "cancelled"


def test_declare_decision_preserves_concurrent_title(canvas_tmp_root):
    """declare_decision must merge its new decision into the freshest meta,
    preserving a concurrent title bump."""
    store.open_canvas("plan-x", title="Plan X")
    concurrent_ts = datetime(2031, 2, 2, tzinfo=timezone.utc)

    def interleave(name):
        current = store.read_meta(name)
        store.write_meta(
            name,
            current.model_copy(
                update={"title": "Renamed Mid-Declare", "last_updated": concurrent_ts}
            ),
        )

    store._set_decision_merge_hook(interleave)
    try:
        result = store.declare_decision(
            "plan-x", "d1", "approve", "Ship?", None, "sess-1", "tok-1"
        )
    finally:
        store._set_decision_merge_hook(None)

    assert result == DecisionCode.ACCEPTED
    meta = store.read_meta("plan-x")
    assert meta.title == "Renamed Mid-Declare"
    assert meta.decision is not None
    assert meta.decision.decision_id == "d1"
    assert meta.decision.status == "pending"


def test_cancel_decision_preserves_concurrent_title(canvas_tmp_root):
    """cancel_decision must merge into the freshest meta, preserving a
    concurrent title bump that lands between its read and its write."""
    _seed_decision("plan-x", "d1")
    concurrent_ts = datetime(2032, 3, 3, tzinfo=timezone.utc)

    def interleave(name):
        current = store.read_meta(name)
        store.write_meta(
            name,
            current.model_copy(
                update={"title": "Renamed Mid-Cancel", "last_updated": concurrent_ts}
            ),
        )

    store._set_decision_merge_hook(interleave)
    try:
        result = store.cancel_decision("plan-x", "d1")
    finally:
        store._set_decision_merge_hook(None)

    assert result == DecisionCode.CANCELLED
    meta = store.read_meta("plan-x")
    assert meta.title == "Renamed Mid-Cancel"
    assert meta.last_updated == concurrent_ts
    assert meta.decision.status == "cancelled"


def test_claim_consume_preserves_concurrent_title(canvas_tmp_root):
    """claim_consume's consumed-status write must merge into the freshest
    meta, preserving a concurrent title bump."""
    _land_submission("plan-x", "d1")
    concurrent_ts = datetime(2033, 4, 4, tzinfo=timezone.utc)

    def interleave(name):
        current = store.read_meta(name)
        store.write_meta(
            name,
            current.model_copy(
                update={"title": "Renamed Mid-Consume", "last_updated": concurrent_ts}
            ),
        )

    store._set_decision_merge_hook(interleave)
    try:
        result = store.claim_consume("plan-x", "d1")
    finally:
        store._set_decision_merge_hook(None)

    assert result == store.ConsumeResult(
        DecisionCode.CONSUMED_NOW, _item("plan-x", "d1", "a")
    )
    meta = store.read_meta("plan-x")
    assert meta.title == "Renamed Mid-Consume"
    assert meta.last_updated == concurrent_ts
    assert meta.decision.status == "consumed"


# ---------------------------------------------------------------------------
# Code-review F3: non-serializable submission item must not raise
# ---------------------------------------------------------------------------


def test_claim_submission_non_serializable_value(canvas_tmp_root):
    """A submission item carrying a non-JSON-serializable value returns
    INVALID_VALUE instead of letting ``json.dumps`` raise ``TypeError``, and
    lands no inbox file."""
    _seed_decision("plan-x", "d1")
    item = _item("plan-x", "d1", "a")
    item["extra"] = {1, 2, 3}  # a set is not JSON-serializable
    result = store.claim_submission("plan-x", "d1", item)
    assert result == DecisionCode.INVALID_VALUE
    inbox = os.path.join(store._resolve_canvas_root(), "plan-x", "inbox", "d1.json")
    assert os.path.exists(inbox) is False


# ---------------------------------------------------------------------------
# Code-review F5: validate_submission_value guards None / malformed decision
# ---------------------------------------------------------------------------


def test_validate_submission_value_none_decision():
    """A None decision returns False per the 'any other kind returns False'
    contract, rather than raising AttributeError."""
    assert validate_submission_value(None, "approved") is False


def test_validate_submission_value_malformed_decision():
    """A decision-like object missing ``kind`` returns False, not raising."""

    class _Malformed:
        pass  # no .kind attribute

    assert validate_submission_value(_Malformed(), "approved") is False


# ---------------------------------------------------------------------------
# Gemini round-4: a failed write/flush/fsync after the O_EXCL create must not
# leave a partial/empty inbox file behind. If it did, the corrupt file would
# permanently burn the first-wins claim — every subsequent valid submission
# would see the existing path and return ALREADY_DECIDED, and the submit side
# (unlike the consume side's CORRUPT_SUBMISSION path) has no recovery. A failed
# write must RELEASE the claim: unlink the partial file before re-raising, so a
# retry can win cleanly.
# ---------------------------------------------------------------------------


def test_claim_submission_failed_fsync_releases_claim(canvas_tmp_root):
    """If ``os.fsync`` raises after the O_EXCL create (disk full, interruption),
    ``claim_submission`` must NOT leave a partial inbox file: the exception
    propagates, ``inbox_path`` does not exist afterward, and a SECOND claim with
    a valid payload wins (ACCEPTED) and persists the COMPLETE bytes.

    The fsync failure is injected with tripwire (the project's mandated mocking
    framework — ``.gemini/styleguide.md`` forbids ``monkeypatch.setattr`` for
    replacing module-level callables): ``os.fsync`` as imported by the store is
    mocked to raise inside the sandbox. The retry runs OUTSIDE the sandbox so it
    exercises the real ``os.fsync`` and proves the byte-for-byte durable write.
    """
    _seed_decision("plan-x", "d1")
    inbox = os.path.join(store._resolve_canvas_root(), "plan-x", "inbox", "d1.json")

    mock_fsync = tripwire.mock("spellbook.canvas.store:os.fsync")
    mock_fsync.raises(OSError("simulated fsync failure (disk full)"))

    # The failed durability step propagates (the route would 500). The claim
    # must not be silently consumed.
    with tripwire:
        with pytest.raises(OSError, match="simulated fsync failure"):
            store.claim_submission("plan-x", "d1", _item("plan-x", "d1", "a"))

    # The mock fired exactly on the durability step: os.fsync(fileno) is called
    # with the single inbox-file descriptor (an int). The fd value is OS-assigned
    # and unknowable, so match its type — but the call MUST have happened (a fix
    # that skipped fsync entirely, or fsynced a different fd count, would fail).
    # ``raised`` is required because the mock used ``.raises``; the propagated
    # OSError instance is the one we injected (message asserted via pytest.raises).
    mock_fsync.assert_call(args=(IsInstance(int),), raised=IsInstance(OSError))

    # The partial/empty file was unlinked: the claim slot is free again, not
    # burned with a corrupt payload.
    assert os.path.exists(inbox) is False

    # A retry with a valid payload (real fsync, OUTSIDE the sandbox) must win
    # cleanly and persist the complete bytes byte-for-byte (not a truncated
    # prefix from the prior aborted attempt).
    retry_item = _item("plan-x", "d1", "b")
    result = store.claim_submission("plan-x", "d1", retry_item)
    assert result == DecisionCode.ACCEPTED
    expected = json.dumps(retry_item).encode("utf-8")
    with open(inbox, "rb") as fh:
        assert fh.read() == expected
