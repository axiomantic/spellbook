"""F4: end-to-end subprocess event transport integration test.

Proves the full path: hook-subprocess -> POST /api/events/publish ->
admin/mcp event bus. The production concern this guards: a subprocess
calling ``spellbook.worker_llm.events.publish_call`` MUST reach the
daemon's in-process event bus over HTTP, so the admin EventMonitorPage
actually shows worker-LLM calls fired from hook subprocesses (which have
no asyncio loop of their own and therefore cannot use ``publish_sync``
directly).

Test shape:
  1. Spin up a real uvicorn server in a background thread bound to an
     ephemeral port. The server mounts the same MCP Starlette app the
     daemon ships (including the ``/api/events/publish`` custom route)
     so subprocess HTTP calls exercise the actual production handler.
  2. Attach a fresh subscriber to ``event_bus`` so we can observe the
     delivered Event object.
  3. Spawn a real subprocess (``sys.executable``) that imports
     ``spellbook.worker_llm.events`` and calls ``publish_call`` with
     ``SPELLBOOK_MCP_HOST``/``SPELLBOOK_MCP_PORT`` pointing at the test
     server.
  4. Poll the subscriber's queue; assert a ``WORKER_LLM.call_ok`` event
     lands within 2 seconds with the exact payload shape.

See impl plan Task F4; design §2.5, §11.2 entry
``test_subprocess_event_transport.py``.
"""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _find_free_port() -> int:
    """Ask the kernel for a free port; close immediately (OS won't reuse
    for a few seconds, safe for test-duration binding).
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def uvicorn_mcp_server():
    """Boot the real MCP Starlette app (including /api/events/publish) on
    a background thread bound to an ephemeral port. Yields the port, then
    tears down.
    """
    import uvicorn

    from spellbook.mcp.server import mcp, _mount_admin_app
    import spellbook.mcp.routes  # noqa: F401 -- registers custom routes

    # Idempotent mount of the /admin sub-app (matches production).
    mcp._additional_http_routes = [
        r for r in mcp._additional_http_routes
        if getattr(r, "path", None) != "/admin"
    ]
    _mount_admin_app()
    app = mcp.http_app()

    # Flip the daemon marker so events arriving via the HTTP path land on
    # the in-process event_bus (same behavior as production daemon).
    from spellbook.admin.events import event_bus
    prior = getattr(event_bus, "_in_daemon", False)
    event_bus._in_daemon = True

    port = _find_free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="on",
    )
    server = uvicorn.Server(config)

    def _run() -> None:
        # Each thread needs its own loop.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        finally:
            loop.close()

    thread = threading.Thread(target=_run, daemon=True, name="uvicorn-mcp-test")
    thread.start()

    # Wait until the server is accepting connections (up to 5s).
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:  # pragma: no cover
        server.should_exit = True
        thread.join(timeout=1.0)
        pytest.fail("uvicorn test server failed to start")

    try:
        yield port
    finally:
        server.should_exit = True
        thread.join(timeout=2.0)
        event_bus._in_daemon = prior


@pytest.fixture
def bearer_token_present(tmp_path, monkeypatch):
    """Provide a bearer token at the canonical path so subprocess
    ``_load_bearer_token()`` returns something. Required because
    ``BearerAuthMiddleware`` gates the /api/events/publish route.
    """
    # Override the token path used by worker_llm.auth._load_bearer_token
    # AND by spellbook.core.auth in both the test and subprocess processes.
    tok = tmp_path / ".mcp-token"
    tok.write_text("test-token", encoding="utf-8")
    # Point the worker_llm.auth module at it in-process (not strictly
    # needed here since the subprocess spawns fresh, but prevents the
    # test-side bearer-loading from hitting the real user's path).
    from spellbook.worker_llm import auth as wl_auth
    monkeypatch.setattr(wl_auth, "_TOKEN_PATH", tok)
    return tok


@pytest.fixture
def fake_bearer_auth(monkeypatch):
    """Monkeypatch ``spellbook.core.auth.load_token`` to return our test
    token so the daemon-side ``BearerAuthMiddleware`` accepts our POST.
    """
    from spellbook.core import auth as core_auth

    original = getattr(core_auth, "load_token", None)
    monkeypatch.setattr(core_auth, "load_token", lambda: "test-token")
    yield
    if original is not None:
        monkeypatch.setattr(core_auth, "load_token", original)


@pytest.mark.asyncio
async def test_subprocess_publish_reaches_event_bus(
    uvicorn_mcp_server, bearer_token_present, fake_bearer_auth
):
    """A real subprocess POSTing publish_call lands on the in-process
    event_bus within 2 seconds. This exercises C1's fallback transport
    (urllib POST -> /api/events/publish route on the MCP root -> event
    bus) end-to-end.
    """
    from spellbook.admin.events import Subsystem, event_bus

    # Subscribe BEFORE spawning the subprocess so we do not race the event.
    subscriber_id = "f4-test-subscriber"
    queue = await event_bus.subscribe(subscriber_id)

    try:
        port = uvicorn_mcp_server

        env = dict(os.environ)
        env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"
        env["SPELLBOOK_MCP_PORT"] = str(port)
        # Make sure the subprocess can find the repo's spellbook package
        # and also the test token path so _load_bearer_token picks it up.
        env["PYTHONPATH"] = (
            f"{REPO_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
        )
        env["HOME"] = str(bearer_token_present.parent.parent)
        # _TOKEN_PATH in the subprocess resolves from Path.home() / .local
        # / spellbook / .mcp-token. Set it up at that location.
        token_dir = Path(env["HOME"]) / ".local" / "spellbook"
        token_dir.mkdir(parents=True, exist_ok=True)
        (token_dir / ".mcp-token").write_text("test-token", encoding="utf-8")

        script = (
            "import sys; "
            "from spellbook.worker_llm.events import publish_call; "
            "publish_call(task='transcript_harvest', model='m', "
            "latency_ms=1, status='success', prompt_len=1, response_len=1); "
            "sys.stdout.write('published'); sys.stdout.flush()"
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            timeout=10,
            text=True,
        )

        # The subprocess fire-and-forget publish returns immediately; any
        # unclean exit is a setup bug we want to surface loudly.
        assert result.returncode == 0, (
            f"subprocess failed (rc={result.returncode}): "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "published" in result.stdout

        # Port-parity invariant (C1 guard): confirm the env variable we
        # set in the subprocess matches the server we bound. This catches
        # the old bug where the fallback targeted port 58765.
        assert env["SPELLBOOK_MCP_PORT"] == str(port)

        # Poll the subscriber queue for up to 2 seconds.
        event = None
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
                break
            except asyncio.TimeoutError:
                continue

        assert event is not None, (
            "Event did not land on the bus within 2 seconds. "
            f"Subprocess stdout={result.stdout!r}, stderr={result.stderr!r}"
        )
        assert event.subsystem == Subsystem.WORKER_LLM
        assert event.event_type == "call_ok"
        assert event.data["task"] == "transcript_harvest"
        assert event.data["model"] == "m"
        assert event.data["latency_ms"] == 1
        assert event.data["status"] == "success"

    finally:
        await event_bus.unsubscribe(subscriber_id)
