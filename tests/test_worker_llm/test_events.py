"""Tests for ``spellbook.worker_llm.events`` hybrid publisher."""

import sys
from contextlib import contextmanager
from pathlib import Path

import bigfoot
import pytest
from dirty_equals import AnyThing, IsInstance
from sqlalchemy import create_engine, select

from spellbook.admin.events import Event, Subsystem, event_bus
from spellbook.db.engines import get_sync_session
from spellbook.db.spellbook_models import SpellbookBase, WorkerLLMCall
from spellbook.worker_llm import events as wl_events
from spellbook.worker_llm import observability as wl_obs


def _capture_publish_sync(captured: list):
    """Return a fake publish_sync that records the Event it receives."""

    def _fake(evt):
        captured.append(evt)

    return _fake


def test_in_daemon_uses_publish_sync(monkeypatch):
    monkeypatch.setattr(event_bus, "_in_daemon", True)
    captured: list = []
    pm = bigfoot.mock("spellbook.worker_llm.events:publish_sync")
    pm.calls(_capture_publish_sync(captured))

    with bigfoot:
        wl_events.publish_call(
            task="t",
            model="m",
            latency_ms=1,
            status="ok",
            prompt_len=1,
            response_len=1,
        )

    pm.assert_call(args=(IsInstance(Event),), kwargs={})
    assert len(captured) == 1
    evt = captured[0]
    assert evt.subsystem == Subsystem.WORKER_LLM
    assert evt.event_type == "call_ok"
    assert evt.data == {
        "task": "t",
        "model": "m",
        "latency_ms": 1,
        "status": "ok",
        "prompt_len": 1,
        "response_len": 1,
        "error": None,
        "override_loaded": False,
    }


def test_in_daemon_publishes_override_loaded(monkeypatch):
    monkeypatch.setattr(event_bus, "_in_daemon", True)
    captured: list = []
    pm = bigfoot.mock("spellbook.worker_llm.events:publish_sync")
    pm.calls(_capture_publish_sync(captured))

    with bigfoot:
        wl_events.publish_override_loaded(task="tool_safety", path="/tmp/x.md")

    pm.assert_call(args=(IsInstance(Event),), kwargs={})
    assert len(captured) == 1
    evt = captured[0]
    assert evt.subsystem == Subsystem.WORKER_LLM
    assert evt.event_type == "override_loaded"
    assert evt.data == {"task": "tool_safety", "path": "/tmp/x.md"}


def test_error_emits_call_failed_event(monkeypatch):
    monkeypatch.setattr(event_bus, "_in_daemon", True)
    captured: list = []
    pm = bigfoot.mock("spellbook.worker_llm.events:publish_sync")
    pm.calls(_capture_publish_sync(captured))

    with bigfoot:
        wl_events.publish_call(
            task="t",
            model="m",
            latency_ms=42,
            status="WorkerLLMTimeout",
            prompt_len=100,
            response_len=0,
            error="boom",
            override_loaded=True,
        )

    pm.assert_call(args=(IsInstance(Event),), kwargs={})
    assert len(captured) == 1
    evt = captured[0]
    assert evt.event_type == "call_failed"
    assert evt.data == {
        "task": "t",
        "model": "m",
        "latency_ms": 42,
        "status": "WorkerLLMTimeout",
        "prompt_len": 100,
        "response_len": 0,
        "error": "boom",
        "override_loaded": True,
    }


def test_publish_call_fail_open_event_type(monkeypatch):
    """``status='fail_open'`` routes to ``event_type='call_fail_open'``.

    The fail-open branch must take precedence over the ``error`` truthy
    branch: even when ``error`` is a non-empty string (as produced by the
    ``tool_safety`` prompt-load short-circuit), the emitted event type is
    ``call_fail_open``, NOT ``call_failed``. Design §4.1 + Step 4 of the
    impl plan — separating event types is load-bearing for the subscriber
    audit and DB write path.
    """
    monkeypatch.setattr(event_bus, "_in_daemon", True)
    captured: list = []
    pm = bigfoot.mock("spellbook.worker_llm.events:publish_sync")
    pm.calls(_capture_publish_sync(captured))

    with bigfoot:
        wl_events.publish_call(
            task="tool_safety",
            model="",
            latency_ms=0,
            status="fail_open",
            prompt_len=0,
            response_len=0,
            error="prompt_load_error: boom",
        )

    pm.assert_call(args=(IsInstance(Event),), kwargs={})
    assert len(captured) == 1
    evt = captured[0]
    assert evt.subsystem == Subsystem.WORKER_LLM
    assert evt.event_type == "call_fail_open"
    assert evt.data == {
        "task": "tool_safety",
        "model": "",
        "latency_ms": 0,
        "status": "fail_open",
        "prompt_len": 0,
        "response_len": 0,
        "error": "prompt_load_error: boom",
        "override_loaded": False,
    }


def test_subprocess_posts_to_daemon(monkeypatch):
    monkeypatch.setattr(event_bus, "_in_daemon", False)
    calls: list = []

    def fake_post(path, payload, timeout=1.0):
        calls.append((path, payload, timeout))

    fallback = bigfoot.mock("spellbook.worker_llm.events:_fallback_http_post")
    fallback.calls(fake_post)
    # Force the lazy import of hooks.spellbook_hook to fail so the fallback
    # helper is the one invoked.
    monkeypatch.setitem(sys.modules, "hooks.spellbook_hook", None)

    with bigfoot:
        wl_events.publish_call(
            task="t",
            model="m",
            latency_ms=1,
            status="err",
            prompt_len=1,
            response_len=0,
            error="boom",
        )

    fallback.assert_call(
        args=("/api/events/publish", AnyThing), kwargs={"timeout": 1.0}
    )
    assert len(calls) == 1
    path, payload, timeout = calls[0]
    assert path == "/api/events/publish"
    assert timeout == 1.0
    assert payload == {
        "subsystem": "worker_llm",
        "event_type": "call_failed",
        "data": {
            "task": "t",
            "model": "m",
            "latency_ms": 1,
            "status": "err",
            "prompt_len": 1,
            "response_len": 0,
            "error": "boom",
            "override_loaded": False,
        },
    }


def test_subprocess_override_loaded_posts_to_daemon(monkeypatch):
    monkeypatch.setattr(event_bus, "_in_daemon", False)
    calls: list = []

    fallback = bigfoot.mock("spellbook.worker_llm.events:_fallback_http_post")
    fallback.calls(
        lambda path, payload, timeout=1.0: calls.append((path, payload, timeout))
    )
    monkeypatch.setitem(sys.modules, "hooks.spellbook_hook", None)

    with bigfoot:
        wl_events.publish_override_loaded(task="transcript_harvest", path="/u/x.md")

    fallback.assert_call(
        args=("/api/events/publish", AnyThing), kwargs={"timeout": 1.0}
    )
    assert calls == [
        (
            "/api/events/publish",
            {
                "subsystem": "worker_llm",
                "event_type": "override_loaded",
                "data": {"task": "transcript_harvest", "path": "/u/x.md"},
            },
            1.0,
        )
    ]


def test_fallback_http_post_defaults_to_port_8765(monkeypatch):
    # Clear any env var leakage, then simulate urllib to capture URL.
    monkeypatch.delenv("SPELLBOOK_MCP_PORT", raising=False)
    monkeypatch.delenv("SPELLBOOK_MCP_HOST", raising=False)

    captured: list = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=1.0):
        captured.append((req.full_url, timeout))
        return _FakeResponse()

    urlopen_mock = bigfoot.mock("urllib.request:urlopen")
    urlopen_mock.calls(fake_urlopen)

    with bigfoot:
        wl_events._fallback_http_post("/api/events/publish", {"x": 1}, timeout=1.0)

    urlopen_mock.assert_call(args=(AnyThing,), kwargs={"timeout": 1.0})
    assert captured == [("http://127.0.0.1:8765/api/events/publish", 1.0)]


def test_fallback_http_post_respects_env_overrides(monkeypatch):
    monkeypatch.setenv("SPELLBOOK_MCP_HOST", "example.local")
    monkeypatch.setenv("SPELLBOOK_MCP_PORT", "12345")

    captured: list = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=1.0):
        captured.append(req.full_url)
        return _FakeResponse()

    urlopen_mock = bigfoot.mock("urllib.request:urlopen")
    urlopen_mock.calls(fake_urlopen)

    with bigfoot:
        wl_events._fallback_http_post("/p", {"x": 1}, timeout=1.0)

    urlopen_mock.assert_call(args=(AnyThing,), kwargs={"timeout": 1.0})
    assert captured == ["http://example.local:12345/p"]


def test_fallback_http_post_swallows_all_exceptions(monkeypatch):
    monkeypatch.delenv("SPELLBOOK_MCP_PORT", raising=False)
    # Reset the module-level counter so this test's loud-first-warning
    # behavior is order-independent.
    monkeypatch.setattr(wl_events, "_publish_failures", 0)

    def raising_urlopen(*a, **kw):
        raise ConnectionRefusedError("nope")

    urlopen_mock = bigfoot.mock("urllib.request:urlopen")
    urlopen_mock.calls(raising_urlopen)

    with bigfoot:
        # Must not raise.
        wl_events._fallback_http_post("/p", {"x": 1}, timeout=1.0)

    urlopen_mock.assert_call(args=(AnyThing,), kwargs={"timeout": 1.0})
    # The first publish failure emits one WARNING via the module logger;
    # bigfoot's log plugin records it and requires explicit assertion.
    bigfoot.log_mock.assert_log(
        level="WARNING",
        message=AnyThing,
        logger_name="spellbook.worker_llm.events",
    )


def test_fallback_http_post_warns_exactly_once_across_failures(monkeypatch, caplog):
    """First failure -> WARNING; subsequent failures -> DEBUG.

    Review finding I3: silent swallow of subprocess publish failures hid a
    route-mismatch bug for a long time. We keep fire-and-forget semantics
    (never raise, never spam) but make the FIRST failure loud so the next
    such misconfiguration gets caught in operator logs.

    Bigfoot's ``LoggingPlugin`` intercepts every ``logger.log()`` call and
    requires that each be asserted. We still use ``caplog.at_level(DEBUG)``
    to raise the module logger's effective level above the default WARNING
    so the DEBUG calls actually reach ``Logger._log`` (and therefore the
    bigfoot interceptor) -- otherwise the DEBUGs get filtered out before
    bigfoot can see them.
    """
    import logging

    from dirty_equals import IsStr

    monkeypatch.delenv("SPELLBOOK_MCP_PORT", raising=False)
    monkeypatch.delenv("SPELLBOOK_MCP_HOST", raising=False)
    # Reset the module-level counter so this test is order-independent.
    # ``_publish_failures`` is an int counter, not a callable; monkeypatch is
    # appropriate per the bigfoot-callable-only rule.
    monkeypatch.setattr(wl_events, "_publish_failures", 0)

    def raising_urlopen(*a, **kw):
        raise ConnectionRefusedError("no daemon")

    urlopen_mock = bigfoot.mock("urllib.request:urlopen")
    for _ in range(5):
        urlopen_mock.calls(raising_urlopen)

    with caplog.at_level(logging.DEBUG, logger="spellbook.worker_llm.events"):
        with bigfoot:
            for _ in range(5):
                wl_events._fallback_http_post(
                    "/api/events/publish", {"x": 1}, timeout=1.0
                )

    # Assertion strategy: the 5 urlopen calls and 5 log emissions are
    # interleaved in wall-clock order. Wrap in ``in_any_order`` so we do
    # not have to encode the interleaving; bigfoot only requires that
    # every interaction be asserted, not that they be asserted in timeline
    # order.
    warning_msg_pattern = IsStr(
        regex=r".*ConnectionRefusedError.*/api/events/publish.*",
    )
    debug_msg = (
        "worker_llm event publish failed (subprocess fallback) to "
        "http://127.0.0.1:8765/api/events/publish"
    )
    with bigfoot.in_any_order():
        for _ in range(5):
            urlopen_mock.assert_call(args=(AnyThing,), kwargs={"timeout": 1.0})
        # First failure: loud warning naming the exception and URL.
        bigfoot.log_mock.assert_log(
            level="WARNING",
            message=warning_msg_pattern,
            logger_name="spellbook.worker_llm.events",
        )
        # Failures 2..5: quiet DEBUG so we do not spam operator logs.
        for _ in range(4):
            bigfoot.log_mock.assert_log(
                level="DEBUG",
                message=debug_msg,
                logger_name="spellbook.worker_llm.events",
            )


def test_fallback_http_post_attaches_bearer_token_when_present(
    monkeypatch, tmp_path
):
    """The MCP-root ``/api/events/publish`` route is behind
    ``BearerAuthMiddleware``. Subprocess callers must attach the bearer
    token from ``~/.local/spellbook/.mcp-token`` or every publish will 401.
    """
    token_file = tmp_path / ".mcp-token"
    token_file.write_text("secret-token-abc")
    # ``_TOKEN_PATH`` is a ``Path`` object, not a callable; monkeypatch is
    # appropriate per the bigfoot-callable-only rule.
    monkeypatch.setattr(wl_events, "_TOKEN_PATH", token_file)
    monkeypatch.delenv("SPELLBOOK_MCP_PORT", raising=False)
    monkeypatch.delenv("SPELLBOOK_MCP_HOST", raising=False)

    captured: list = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=1.0):
        captured.append(dict(req.headers))
        return _FakeResponse()

    urlopen_mock = bigfoot.mock("urllib.request:urlopen")
    urlopen_mock.calls(fake_urlopen)

    with bigfoot:
        wl_events._fallback_http_post("/api/events/publish", {"x": 1}, timeout=1.0)

    urlopen_mock.assert_call(args=(AnyThing,), kwargs={"timeout": 1.0})
    assert len(captured) == 1
    # urllib normalizes header names to Title-Case.
    auth_header = captured[0].get("Authorization") or captured[0].get("authorization")
    assert auth_header == "Bearer secret-token-abc"


def test_fallback_http_post_no_auth_header_when_token_missing(
    monkeypatch, tmp_path
):
    """Token file absent: no Authorization header (request will 401; that's
    a deployment misconfiguration, not something we can fake)."""
    # ``_TOKEN_PATH`` is a ``Path`` object, not a callable; monkeypatch stays.
    monkeypatch.setattr(wl_events, "_TOKEN_PATH", tmp_path / "does-not-exist")
    monkeypatch.delenv("SPELLBOOK_MCP_PORT", raising=False)
    monkeypatch.delenv("SPELLBOOK_MCP_HOST", raising=False)

    captured: list = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=1.0):
        captured.append(dict(req.headers))
        return _FakeResponse()

    urlopen_mock = bigfoot.mock("urllib.request:urlopen")
    urlopen_mock.calls(fake_urlopen)

    with bigfoot:
        wl_events._fallback_http_post("/api/events/publish", {"x": 1}, timeout=1.0)

    urlopen_mock.assert_call(args=(AnyThing,), kwargs={"timeout": 1.0})
    assert len(captured) == 1
    assert "Authorization" not in captured[0]
    assert "authorization" not in captured[0]


# ---------------------------------------------------------------------------
# Step 6: ``publish_call`` invokes ``record_call`` (daemon path only).
# ---------------------------------------------------------------------------


@pytest.fixture
def record_call_db(tmp_path: Path, monkeypatch):
    """Create a tmp-file sqlite DB with the ``worker_llm_calls`` table and
    redirect ``observability.get_spellbook_sync_session`` to it.

    Mirrors ``tests/test_worker_llm/test_observability.py::fresh_db`` so the
    real ORM insert path is exercised without touching the user's spellbook.db.
    We do NOT bigfoot-mock ``record_call`` itself: the orchestrator's T4
    contract is "publish_call triggers record_call with the same args AND
    produces a row in the DB", so we verify the row contents directly.
    """
    db_path = str(tmp_path / "spellbook.db")

    engine = create_engine(f"sqlite:///{db_path}")
    SpellbookBase.metadata.create_all(engine)
    engine.dispose()

    @contextmanager
    def _tmp_session():
        with get_sync_session(db_path) as session:
            yield session

    monkeypatch.setattr(wl_obs, "get_spellbook_sync_session", _tmp_session)
    # Reset the observability failure counter so the log policy is test-local.
    monkeypatch.setattr(wl_obs, "_record_call_failures", 0)
    return db_path


def test_publish_call_daemon_path_records_call(
    monkeypatch, record_call_db,
):
    """T4: In-daemon ``publish_call`` writes a row to ``worker_llm_calls``.

    ESCAPE: test_publish_call_daemon_path_records_call
      CLAIM:    publish_call, in-daemon, invokes record_call with the same
                kwargs and produces exactly one worker_llm_calls row whose
                columns match the call arguments.
      PATH:     publish_call -> _publish (publish_sync) -> record_call ->
                observability session.add -> commit.
      CHECK:    (a) publish_sync received the expected Event; (b) exactly one
                row exists in worker_llm_calls; (c) every column on the row
                equals the publish_call kwarg of the same name.
      MUTATION: If publish_call forgot to call record_call, row count == 0
                fails. If record_call were invoked with wrong kwargs (e.g. a
                dropped ``override_loaded``), the full-equality to_dict check
                catches it. If the event publish were dropped, the
                publish_sync bigfoot assertion fails.
      ESCAPE:   A no-op wiring that logs-but-doesn't-write is caught by the
                row-count check. Passing the wrong arg (e.g. error="" instead
                of None) is caught by the full-equality to_dict check.
      IMPACT:   Without this wiring the observability dashboard is empty even
                though events flow correctly — the whole point of Step 6.
    """
    monkeypatch.setattr(event_bus, "_in_daemon", True)
    captured: list = []
    pm = bigfoot.mock("spellbook.worker_llm.events:publish_sync")
    pm.calls(_capture_publish_sync(captured))

    with bigfoot:
        wl_events.publish_call(
            task="transcript_harvest",
            model="gpt-test",
            latency_ms=321,
            status="success",
            prompt_len=10,
            response_len=20,
            error=None,
            override_loaded=True,
        )

    # Event was published.
    pm.assert_call(args=(IsInstance(Event),), kwargs={})
    assert len(captured) == 1
    assert captured[0].event_type == "call_ok"

    # Row was written to worker_llm_calls.
    with get_sync_session(record_call_db) as session:
        rows = session.execute(select(WorkerLLMCall)).scalars().all()

    assert len(rows) == 1
    row = rows[0].to_dict()
    ts = row.pop("timestamp")
    assert ts.endswith("+00:00")  # datetime.now(UTC).isoformat() marker
    assert row == {
        "id": 1,
        "task": "transcript_harvest",
        "model": "gpt-test",
        "status": "success",
        "latency_ms": 321,
        "prompt_len": 10,
        "response_len": 20,
        "error": None,
        "override_loaded": True,
    }


def test_publish_call_subprocess_path_does_not_record_call(
    monkeypatch, record_call_db,
):
    """T5: Subprocess-path ``publish_call`` does NOT call ``record_call``.

    ESCAPE: test_publish_call_subprocess_path_does_not_record_call
      CLAIM:    When ``_in_daemon`` is False, publish_call routes via HTTP
                (``_publish_via_daemon``) and does NOT invoke record_call in
                this process, preventing double-writes once Step 8 lands the
                subprocess-side record_call on /api/events/publish.
      PATH:     publish_call -> _publish -> _publish_via_daemon (HTTP) ->
                (no record_call invocation).
      CHECK:    (a) subprocess HTTP fallback received the publish payload;
                (b) zero rows in worker_llm_calls.
      MUTATION: If the daemon gate were missing, publish_call would also call
                record_call in the subprocess and the row count would be 1.
                If the subprocess HTTP path were broken, the fallback mock
                would not be invoked.
      ESCAPE:   An implementation that ALWAYS calls record_call would write
                a row here — row count > 0 catches it. An implementation
                gated on the wrong condition (e.g. ``not _in_daemon_process``)
                would also write a row.
      IMPACT:   Without the gate, every subprocess publish would produce TWO
                observability rows (one here, one from the /api/events/publish
                route handler in Step 8), doubling every metric.
    """
    monkeypatch.setattr(event_bus, "_in_daemon", False)
    calls: list = []
    fallback = bigfoot.mock("spellbook.worker_llm.events:_fallback_http_post")
    fallback.calls(
        lambda path, payload, timeout=1.0: calls.append((path, payload, timeout))
    )
    # Force the lazy import of hooks.spellbook_hook to fail so the fallback
    # helper is the one invoked (matches test_subprocess_posts_to_daemon).
    monkeypatch.setitem(sys.modules, "hooks.spellbook_hook", None)

    with bigfoot:
        wl_events.publish_call(
            task="tool_safety",
            model="m",
            latency_ms=5,
            status="success",
            prompt_len=1,
            response_len=2,
        )

    # HTTP fallback was used.
    fallback.assert_call(
        args=("/api/events/publish", AnyThing), kwargs={"timeout": 1.0}
    )
    assert len(calls) == 1
    # NO row in worker_llm_calls: record_call must be skipped on subprocess path.
    with get_sync_session(record_call_db) as session:
        rows = session.execute(select(WorkerLLMCall)).scalars().all()
    assert rows == []
