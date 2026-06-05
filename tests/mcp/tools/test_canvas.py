"""Tests for ``spellbook.mcp.tools.canvas``.

Covers all four MCP tools (``canvas_open``, ``canvas_write``,
``canvas_close``, ``canvas_list``) including error codes per design §5.2 / §4
and event publishing.

Uses shared fixtures from ``tests/canvas/conftest.py``.
"""

from __future__ import annotations

import pytest

import os

from tests.canvas.conftest import (  # noqa: F401 — re-export pytest fixtures
    canvas_tmp_root,
    mock_ctx,
    mcp_ctx_with_session,
    mcp_ctx_no_session,
    event_subscriber,
)

# Import the wrapped tool functions. FastMCP's ``@mcp.tool()`` decorator
# returns the original callable bound to the registry; the underlying
# Python function is still importable by name.
from spellbook.mcp.tools.canvas import (
    canvas_close,
    canvas_list,
    canvas_open,
    canvas_write,
)
from spellbook.mcp.tools import canvas as canvas_tools
from spellbook.canvas.decision_contract import SUBMISSION_SCHEMA_VERSION


def _expected_canvas_url(name: str) -> str:
    """Construct the expected admin canvas URL INDEPENDENTLY of the production
    ``_canvas_url`` helper, from the documented default host/port (no env
    override is set by these tests). Building it independently — rather than
    calling ``canvas_tools._canvas_url`` — means the equality also catches a
    mutation INSIDE ``_canvas_url`` (wrong scheme, host, port, or path),
    which an oracle that reused the helper would mirror and miss."""
    return f"http://127.0.0.1:8765/admin/canvas/{name}"


# -----------------------------------------------------------------------
# canvas.decision.* event-type constants (Task B1)
# -----------------------------------------------------------------------


def test_canvas_decision_event_types_exist():
    from spellbook.admin import events

    assert events.CANVAS_DECISION_OPENED == "canvas.decision.opened"
    assert events.CANVAS_DECISION_SUBMITTED == "canvas.decision.submitted"
    assert events.CANVAS_DECISION_CONSUMED == "canvas.decision.consumed"
    assert events.CANVAS_DECISION_CANCELLED == "canvas.decision.cancelled"


# -----------------------------------------------------------------------
# canvas_open
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_new_canvas(canvas_tmp_root, mock_ctx, event_subscriber):
    result = await canvas_open(ctx=mock_ctx, name="design")
    # Full result-dict equality. ``created_at``/``last_updated`` are the only
    # genuinely dynamic fields (server clock); anchor them to the actual values
    # and assert the URL via the production ``_canvas_url`` (no ``.endswith``,
    # which would pass on a wrong host/scheme/extra-suffix URL).
    assert result == {
        "status": "opened",
        "name": "design",
        "title": "design",
        "url": _expected_canvas_url("design"),
        "created_at": result["created_at"],
        "last_updated": result["last_updated"],
        "created": True,
    }
    # Exactly one event published with created=True, reopened=False.
    assert len(event_subscriber) == 1
    evt = event_subscriber[0]
    assert evt.subsystem.value == "canvas"
    assert evt.event_type == "canvas.opened"
    assert evt.data == {"canvas": "design", "created": True, "reopened": False}


@pytest.mark.asyncio
async def test_open_idempotent_existing(canvas_tmp_root, mock_ctx, event_subscriber):
    await canvas_open(ctx=mock_ctx, name="design")
    event_subscriber.clear()
    result = await canvas_open(ctx=mock_ctx, name="design")
    assert result["status"] == "opened"
    assert result["created"] is False
    assert len(event_subscriber) == 1
    assert event_subscriber[0].data == {
        "canvas": "design",
        "created": False,
        "reopened": False,
    }


@pytest.mark.asyncio
async def test_open_reopen_closed(canvas_tmp_root, mock_ctx, event_subscriber):
    await canvas_open(ctx=mock_ctx, name="design")
    await canvas_close(ctx=mock_ctx, name="design")
    event_subscriber.clear()
    result = await canvas_open(ctx=mock_ctx, name="design")
    assert result["status"] == "opened"
    assert result["created"] is False
    assert len(event_subscriber) == 1
    assert event_subscriber[0].data == {
        "canvas": "design",
        "created": False,
        "reopened": True,
    }


@pytest.mark.asyncio
async def test_open_invalid_name(canvas_tmp_root, mock_ctx, event_subscriber):
    result = await canvas_open(ctx=mock_ctx, name="../etc")
    assert result["code"] == "invalid_name"
    assert "error" in result
    assert event_subscriber == []  # No publish on error.


# -----------------------------------------------------------------------
# canvas_write
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_happy(canvas_tmp_root, mock_ctx, event_subscriber):
    await canvas_open(ctx=mock_ctx, name="design")
    event_subscriber.clear()
    result = await canvas_write(ctx=mock_ctx, canvas="design", content="# Hello")
    # Full result-dict equality. ``last_updated`` is the only dynamic field
    # (server clock); anchor it and assert the URL via ``_canvas_url``.
    assert result == {
        "status": "written",
        "canvas": "design",
        "page": "index.md",
        "bytes": len(b"# Hello"),
        "last_updated": result["last_updated"],
        "url": _expected_canvas_url("design"),
    }
    assert len(event_subscriber) == 1
    evt = event_subscriber[0]
    assert evt.event_type == "canvas.updated"
    assert evt.data == {"canvas": "design", "page": "index.md", "bytes": 7}


@pytest.mark.asyncio
async def test_write_invalid_name(canvas_tmp_root, mock_ctx):
    result = await canvas_write(ctx=mock_ctx, canvas="../etc", content="x")
    assert result["code"] == "invalid_name"


@pytest.mark.asyncio
async def test_write_not_found(canvas_tmp_root, mock_ctx):
    result = await canvas_write(ctx=mock_ctx, canvas="ghost", content="x")
    assert result["code"] == "not_found"


@pytest.mark.asyncio
async def test_write_closed(canvas_tmp_root, mock_ctx):
    await canvas_open(ctx=mock_ctx, name="design")
    await canvas_close(ctx=mock_ctx, name="design")
    result = await canvas_write(ctx=mock_ctx, canvas="design", content="x")
    assert result["code"] == "closed"


@pytest.mark.asyncio
async def test_write_page_too_large(canvas_tmp_root, mock_ctx, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_CANVAS_MAX_PAGE_BYTES", "10")
    await canvas_open(ctx=mock_ctx, name="design")
    result = await canvas_write(
        ctx=mock_ctx, canvas="design", content="0123456789X"
    )
    assert result["code"] == "page_too_large"


@pytest.mark.asyncio
async def test_write_invalid_content(canvas_tmp_root, mock_ctx):
    await canvas_open(ctx=mock_ctx, name="design")
    result = await canvas_write(
        ctx=mock_ctx, canvas="design", content="x", page="other.md"
    )
    assert result["code"] == "invalid_content"


# -----------------------------------------------------------------------
# canvas_close
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_happy(canvas_tmp_root, mock_ctx, event_subscriber):
    await canvas_open(ctx=mock_ctx, name="design")
    event_subscriber.clear()
    result = await canvas_close(ctx=mock_ctx, name="design")
    # Full result-dict equality. ``last_updated`` is the only dynamic field.
    assert result == {
        "status": "closed",
        "name": "design",
        "last_updated": result["last_updated"],
    }
    assert len(event_subscriber) == 1
    evt = event_subscriber[0]
    assert evt.event_type == "canvas.closed"
    assert evt.data == {"canvas": "design"}


@pytest.mark.asyncio
async def test_close_not_found(canvas_tmp_root, mock_ctx):
    result = await canvas_close(ctx=mock_ctx, name="ghost")
    assert result["code"] == "not_found"


@pytest.mark.asyncio
async def test_close_invalid_name(canvas_tmp_root, mock_ctx):
    result = await canvas_close(ctx=mock_ctx, name="../etc")
    assert result["code"] == "invalid_name"


# -----------------------------------------------------------------------
# canvas_list
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_empty(canvas_tmp_root, mock_ctx, event_subscriber):
    result = await canvas_list(ctx=mock_ctx)
    assert result == {"canvases": [], "count": 0}
    assert event_subscriber == []  # Read-only: no publish.


@pytest.mark.asyncio
async def test_list_populated_sorted_desc(canvas_tmp_root, mock_ctx):
    import asyncio
    await canvas_open(ctx=mock_ctx, name="alpha")
    await asyncio.sleep(0.01)
    await canvas_open(ctx=mock_ctx, name="beta")
    await asyncio.sleep(0.01)
    # Bump alpha by writing to it.
    await canvas_write(ctx=mock_ctx, canvas="alpha", content="fresh")
    result = await canvas_list(ctx=mock_ctx)
    names = [c["name"] for c in result["canvases"]]
    assert names == ["alpha", "beta"]
    assert result["count"] == 2
    # Each item exposes url for the frontend.
    for item in result["canvases"]:
        assert item["url"].startswith("http://")
        assert item["url"].endswith(f"/admin/canvas/{item['name']}")


@pytest.mark.asyncio
async def test_list_corrupt_meta_regenerated(canvas_tmp_root, mock_ctx):
    import os
    await canvas_open(ctx=mock_ctx, name="design")
    meta_path = os.path.join(canvas_tmp_root, "design", "meta.json")
    with open(meta_path, "w") as f:
        f.write("garbage")
    result = await canvas_list(ctx=mock_ctx)
    names = [c["name"] for c in result["canvases"]]
    assert "design" in names


# -----------------------------------------------------------------------
# Threat-model docstring
# -----------------------------------------------------------------------


def _threat_model_block(doc: str) -> str:
    """Extract the literal threat-model paragraph from a docstring.

    The block runs from the line beginning ``Threat model:`` (the paragraph's
    start marker) through to the first blank line. Returning the full literal
    lets the tests assert exact equality on the complete paragraph rather than
    probing for keyword substrings (which pass even if the wording rots, the
    sentences are reordered, or a clause is dropped).

    Each line is left-stripped before re-joining so the comparison targets the
    paragraph *wording*, not the docstring's source indentation. This matters
    because docstring indentation in ``__doc__`` is Python-version-dependent:
    CPython 3.13+ strips the common leading whitespace from docstrings at
    compile time, while 3.11/3.12 preserve the raw four-space indent of lines
    after the first. The threat-model paragraph is flat prose with no
    intentional internal indentation, so per-line lstrip normalizes both forms
    without weakening the exact-wording guarantee."""
    lines = (doc or "").split("\n")
    start = next(
        i for i, line in enumerate(lines)
        if line.lstrip().startswith("Threat model:")
    )
    end = start
    while end < len(lines) and lines[end].strip() != "":
        end += 1
    return "\n".join(line.lstrip() for line in lines[start:end])


def test_threat_model_in_canvas_open_docstring():
    """canvas_open docstring threat-model paragraph matches the §14 posture
    text exactly (full-literal equality, not keyword presence)."""
    assert _threat_model_block(canvas_open.__doc__) == (
        "Threat model: canvas content is TRUSTED-LOCAL-AGENT output. Agents MUST\n"
        "NOT write unsanitized external content (chat transcripts, fetched web\n"
        "pages, untrusted MCP tool outputs) into a canvas. Raw HTML is permitted\n"
        "via rehype-raw and executes under the admin's auth context — a script\n"
        "tag is a session-takeover primitive."
    )


def test_threat_model_in_canvas_write_docstring():
    """canvas_write docstring threat-model paragraph matches the §14 posture
    text exactly (full-literal equality, not keyword presence)."""
    assert _threat_model_block(canvas_write.__doc__) == (
        "Threat model: TRUSTED-LOCAL-AGENT only. Do NOT write unsanitized external\n"
        "content (chat transcripts, fetched web pages, untrusted MCP tool\n"
        "outputs). Raw HTML is rendered via rehype-raw and executes under the\n"
        "admin's auth context."
    )


# -----------------------------------------------------------------------
# Publish error resilience
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_failure_does_not_break_tool(
    canvas_tmp_root, mock_ctx, monkeypatch
):
    """If event_bus.publish raises, the tool still returns success."""
    from spellbook.admin.events import event_bus

    async def _boom(event):
        raise RuntimeError("simulated publish failure")

    monkeypatch.setattr(event_bus, "publish", _boom)
    result = await canvas_open(ctx=mock_ctx, name="design")
    assert result["status"] == "opened"


# -----------------------------------------------------------------------
# canvas_decision_open (Task B2)
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_canvas_decision_open_declares(canvas_tmp_root, mcp_ctx_with_session):
    from spellbook.canvas import store
    store.open_canvas("plan-x", title="Plan X")
    ctx = mcp_ctx_with_session("sess-1")
    result = await canvas_tools.canvas_decision_open(
        ctx, canvas="plan-x", decision_id="d1", kind="choice",
        prompt="Pick", options=[{"value": "a", "label": "A"}, {"value": "b", "label": "B"}],
    )
    # The await_token is server-generated (secrets.token_urlsafe) — genuinely
    # unknowable at test time. Anchor the full result-dict equality to the
    # token the server PERSISTED into the binding, which simultaneously proves
    # the returned token roundtrips to disk (a mutation returning a fresh token
    # while persisting a different one would fail this).
    meta = store.read_meta("plan-x")
    stored_token = meta.decision.await_binding.await_token
    assert result["await_token"] == stored_token
    assert result == {
        "status": "declared",
        "canvas": "plan-x",
        "decision_id": "d1",
        "kind": "choice",
        "await_token": stored_token,
        "url": _expected_canvas_url("plan-x"),
    }
    assert meta.decision.await_binding.session_id == "sess-1"


@pytest.mark.asyncio
async def test_canvas_decision_open_no_session_identity(canvas_tmp_root, mcp_ctx_no_session):
    from spellbook.canvas import store
    store.open_canvas("plan-x", title="Plan X")
    result = await canvas_tools.canvas_decision_open(
        mcp_ctx_no_session, canvas="plan-x", decision_id="d1", kind="approve", prompt="Ship?",
    )
    # De-tautologized: assert the envelope shape, the exact DecisionCode, AND
    # the exact §4.1 contract message.
    assert set(result.keys()) == {"error", "code"}
    assert result["code"] == "no_session_identity"
    assert result["error"] == (
        "No session identity: this context has no MCP session id, so a decision "
        "binding cannot be established. Call canvas_decision_open from the session "
        "main context."
    )
    assert store.read_meta("plan-x").decision is None  # wrote nothing


@pytest.mark.asyncio
async def test_canvas_decision_open_decision_exists(canvas_tmp_root, mcp_ctx_with_session):
    from spellbook.canvas import store
    store.open_canvas("plan-x", title="Plan X")
    ctx = mcp_ctx_with_session("sess-1")
    await canvas_tools.canvas_decision_open(ctx, canvas="plan-x", decision_id="d1",
                                            kind="approve", prompt="Ship?")
    second = await canvas_tools.canvas_decision_open(ctx, canvas="plan-x", decision_id="d2",
                                                     kind="approve", prompt="Again?")
    assert second["code"] == "decision_exists"


@pytest.mark.asyncio
async def test_canvas_decision_open_invalid_options_surfaces_envelope(
    canvas_tmp_root, mcp_ctx_with_session
):
    """Gemini round-5 F1 (tool layer): a structurally malformed option (here a
    non-str value) must surface the clean INVALID_OPTIONS envelope, not crash
    the tool with a TypeError. The store hardens the validation; this proves the
    tool's error envelope conveys it and writes no decision."""
    from spellbook.canvas import store

    store.open_canvas("plan-x", title="Plan X")
    ctx = mcp_ctx_with_session("sess-1")
    result = await canvas_tools.canvas_decision_open(
        ctx,
        canvas="plan-x",
        decision_id="d1",
        kind="choice",
        prompt="Pick",
        options=[{"value": None, "label": "x"}],
    )
    assert result == {
        "error": "options invalid: at most 20, each value/label <=200 chars",
        "code": "invalid_options",
    }
    assert store.read_meta("plan-x").decision is None  # wrote nothing


@pytest.mark.asyncio
async def test_canvas_decision_open_publishes_opened(canvas_tmp_root, mcp_ctx_with_session, event_subscriber):
    from spellbook.canvas import store
    from spellbook.admin import events
    store.open_canvas("plan-x", title="Plan X")
    ctx = mcp_ctx_with_session("sess-1")
    await canvas_tools.canvas_decision_open(ctx, canvas="plan-x", decision_id="d1",
                                            kind="approve", prompt="Ship?")
    # event_subscriber is the captured-publish LIST (tests/canvas/conftest.py),
    # mirroring test_open_new_canvas.
    assert len(event_subscriber) == 1
    evt = event_subscriber[-1]
    assert evt.event_type == events.CANVAS_DECISION_OPENED
    assert evt.data == {"canvas": "plan-x", "decision_id": "d1", "kind": "approve"}


# -----------------------------------------------------------------------
# canvas_decision_await (Task B3)
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_await_returns_pending_on_timeout(canvas_tmp_root, mcp_ctx_with_session):
    from spellbook.canvas import store
    store.open_canvas("plan-x", title="Plan X")
    ctx = mcp_ctx_with_session("sess-1")
    await canvas_tools.canvas_decision_open(ctx, canvas="plan-x", decision_id="d1",
                                            kind="approve", prompt="Ship?")
    result = await canvas_tools.canvas_decision_await(ctx, canvas="plan-x", decision_id="d1", timeout_s=1)
    assert result == {"status": "pending"}


@pytest.mark.asyncio
async def test_await_restart_catchup_disk_preseed(canvas_tmp_root, mcp_ctx_with_session):
    # Submission already on disk BEFORE await (restart catch-up). No event fired.
    from spellbook.canvas import store
    ctx = mcp_ctx_with_session("sess-1")
    store.open_canvas("plan-x", title="Plan X")
    store.declare_decision("plan-x", "d1", "choice",
                           "Q", [{"value": "a", "label": "A"}], "sess-1", "tok-1")
    # mimic the route's claim_submission so binding/token match the stored decision
    meta = store.read_meta("plan-x")
    tok = meta.decision.await_binding.await_token
    store.claim_submission("plan-x", "d1", {
        "schema_version": SUBMISSION_SCHEMA_VERSION, "decision_id": "d1", "canvas": "plan-x",
        "kind": "choice", "value": "a", "free_text": None,
        "await_binding": {"session_id": "sess-1", "await_token": tok},
        "submitted_at": "2026-06-04T18:22:01.001Z", "consumed": False,
    })
    result = await canvas_tools.canvas_decision_await(ctx, canvas="plan-x", decision_id="d1", timeout_s=2)
    assert result["status"] == "submitted"
    assert result["value"] == "a"
    assert result["kind"] == "choice"


@pytest.mark.asyncio
async def test_await_event_driven_wake_no_preseed(canvas_tmp_root, mcp_ctx_with_session):
    # inbox file ABSENT at entry; submission lands DURING the wait; wake via event only.
    #
    # REAL-BUS TEST (I2): this test does NOT take the `event_subscriber` fixture.
    # `event_subscriber` monkeypatches `event_bus.publish` to a no-op list append;
    # with it active the awaiting tool would never wake and the test would hang.
    # Here we let the real `event_bus.publish` fire so the subscription wakes.
    import asyncio
    import time
    from spellbook.canvas import store
    from spellbook.admin import events
    from spellbook.admin.events import event_bus, Event, Subsystem
    ctx = mcp_ctx_with_session("sess-1")
    store.open_canvas("plan-x", title="Plan X")
    store.declare_decision("plan-x", "d1", "choice",
                           "Q", [{"value": "a", "label": "A"}], "sess-1", "tok-1")
    tok = store.read_meta("plan-x").decision.await_binding.await_token
    inbox = os.path.join(store._resolve_canvas_root(), "plan-x", "inbox", "d1.json")
    assert os.path.exists(inbox) is False  # no disk pre-seed at entry

    async def submit_soon():
        await asyncio.sleep(0.2)
        store.claim_submission("plan-x", "d1", {
            "schema_version": SUBMISSION_SCHEMA_VERSION, "decision_id": "d1", "canvas": "plan-x",
            "kind": "choice", "value": "a", "free_text": None,
            "await_binding": {"session_id": "sess-1", "await_token": tok},
            "submitted_at": "2026-06-04T18:22:01.001Z", "consumed": False,
        })
        await event_bus.publish(Event(
            subsystem=Subsystem.CANVAS, event_type=events.CANVAS_DECISION_SUBMITTED,
            data={"canvas": "plan-x", "decision_id": "d1", "value": "a"}))

    start = time.monotonic()
    submit_task = asyncio.create_task(submit_soon())
    result = await canvas_tools.canvas_decision_await(ctx, canvas="plan-x", decision_id="d1", timeout_s=15)
    elapsed = time.monotonic() - start
    await submit_task
    assert result["status"] == "submitted"
    assert result["value"] == "a"
    assert elapsed < 2.0  # event fast-path under 2s SLO


@pytest.mark.asyncio
async def test_await_consumed_idempotent_reawait(canvas_tmp_root, mcp_ctx_with_session):
    from spellbook.canvas import store
    ctx = mcp_ctx_with_session("sess-1")
    store.open_canvas("plan-x", title="Plan X")
    store.declare_decision("plan-x", "d1", "approve", "Ship?", None, "sess-1", "tok-1")
    tok = store.read_meta("plan-x").decision.await_binding.await_token
    store.claim_submission("plan-x", "d1", {
        "schema_version": SUBMISSION_SCHEMA_VERSION, "decision_id": "d1", "canvas": "plan-x",
        "kind": "approve", "value": "approved", "free_text": None,
        "await_binding": {"session_id": "sess-1", "await_token": tok},
        "submitted_at": "2026-06-04T18:22:01.001Z", "consumed": False,
    })
    first = await canvas_tools.canvas_decision_await(ctx, canvas="plan-x", decision_id="d1", timeout_s=2)
    assert first["status"] == "submitted"
    second = await canvas_tools.canvas_decision_await(ctx, canvas="plan-x", decision_id="d1", timeout_s=2)
    assert second == {"status": "consumed"}


@pytest.mark.asyncio
async def test_await_binding_mismatch_wrong_session(canvas_tmp_root, mcp_ctx_with_session):
    from spellbook.canvas import store
    store.open_canvas("plan-x", title="Plan X")
    declarer = mcp_ctx_with_session("sess-1")
    await canvas_tools.canvas_decision_open(declarer, canvas="plan-x", decision_id="d1",
                                            kind="approve", prompt="Ship?")
    other = mcp_ctx_with_session("sess-2")
    result = await canvas_tools.canvas_decision_await(other, canvas="plan-x", decision_id="d1", timeout_s=1)
    assert result["code"] == "binding_mismatch"


@pytest.mark.asyncio
async def test_await_corrupt_submission_recoverable(canvas_tmp_root, mcp_ctx_with_session):
    # Stitch 1: a corrupt inbox JSON file makes claim_consume return
    # DecisionCode.CORRUPT_SUBMISSION (Track A fix 6e6569bf). await must surface
    # the recoverable error envelope naming the inbox path — NOT spin to pending
    # (which would loop forever on an un-repairable file) and NOT burn the marker.
    from spellbook.canvas import store

    ctx = mcp_ctx_with_session("sess-1")
    store.open_canvas("plan-x", title="Plan X")
    store.declare_decision(
        "plan-x", "d1", "approve", "Ship?", None, "sess-1", "tok-1"
    )
    inbox = os.path.join(
        store._resolve_canvas_root(), "plan-x", "inbox", "d1.json"
    )
    with open(inbox, "w", encoding="utf-8") as fh:
        fh.write("{not json")  # corrupt: claim_consume returns CORRUPT_SUBMISSION

    result = await canvas_tools.canvas_decision_await(
        ctx, canvas="plan-x", decision_id="d1", timeout_s=1
    )
    # Exact envelope: {"error", "code"} shape (matches the tool's other error
    # envelopes), code is the DecisionCode wire string, message names the path.
    assert result == {
        "code": "corrupt_submission",
        "error": f"corrupt submission on disk for decision 'd1'; "
        f"repair or remove {inbox} and re-await",
    }
    # Recoverable: the .consumed marker was NOT burned (claim_consume reads
    # before claiming, F1), so a repaired file is still deliverable.
    marker = os.path.join(
        store._resolve_canvas_root(), "plan-x", "inbox", "d1.consumed"
    )
    assert os.path.exists(marker) is False


def test_clamp_timeout_bounds():
    # M4: clamp is a pure module-level helper, asserted directly.
    import spellbook.mcp.tools.canvas as canvas_mod
    assert canvas_mod._clamp_timeout(999) == 20   # over-ceiling clamps down
    assert canvas_mod._clamp_timeout(0) == 1       # under-floor clamps up
    assert canvas_mod._clamp_timeout(15) == 15     # in-range passes through
    assert canvas_mod._clamp_timeout(20) == 20     # ceiling inclusive
    assert canvas_mod._clamp_timeout(1) == 1       # floor inclusive


# -----------------------------------------------------------------------
# canvas_decision_cancel (Task B4)
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_canvas_decision_cancel(canvas_tmp_root, mcp_ctx_with_session, event_subscriber):
    from spellbook.canvas import store
    from spellbook.admin import events
    ctx = mcp_ctx_with_session("sess-1")
    store.open_canvas("plan-x", title="Plan X")
    await canvas_tools.canvas_decision_open(ctx, canvas="plan-x", decision_id="d1",
                                            kind="approve", prompt="Ship?")
    # canvas_decision_open published canvas.decision.opened into the capture
    # list; clear so we assert ONLY the cancel event (mirrors the existing
    # tests' event_subscriber.clear() pattern).
    event_subscriber.clear()
    result = await canvas_tools.canvas_decision_cancel(ctx, canvas="plan-x", decision_id="d1")
    assert result == {"status": "cancelled"}
    assert len(event_subscriber) == 1
    evt = event_subscriber[-1]
    assert evt.event_type == events.CANVAS_DECISION_CANCELLED
    assert evt.data == {"canvas": "plan-x", "decision_id": "d1"}
    assert store.read_meta("plan-x").decision.status == "cancelled"
    # idempotent
    again = await canvas_tools.canvas_decision_cancel(ctx, canvas="plan-x", decision_id="d1")
    assert again == {"status": "cancelled"}


@pytest.mark.asyncio
async def test_canvas_decision_cancel_no_such(canvas_tmp_root, mcp_ctx_with_session):
    from spellbook.canvas import store
    ctx = mcp_ctx_with_session("sess-1")
    store.open_canvas("plan-x", title="Plan X")
    result = await canvas_tools.canvas_decision_cancel(ctx, canvas="plan-x", decision_id="nope")
    assert result["code"] == "no_such_decision"
