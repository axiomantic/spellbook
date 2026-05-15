import asyncio

from fastapi.testclient import TestClient


def test_admin_app_rejects_cross_origin_post():
    """Task 5 contract: ``OriginCheckMiddleware`` is wired into the admin app
    with ``allowed_origins=app.state.allowed_origins``. A state-changing POST
    that presents a valid loopback ``Host`` but a cross-origin ``Origin``
    (and no Bearer) must be rejected with 403 and the plain-text body
    ``"Forbidden: invalid Origin"`` produced by the Origin middleware.

    The Host check (outer) is satisfied by ``Host: 127.0.0.1:8765`` so the
    rejection is unambiguously from the Origin layer, not the Host layer.

    ESCAPE: test_admin_app_rejects_cross_origin_post
      CLAIM: OriginCheckMiddleware is registered on the admin app and runs
             AFTER HostValidator on POSTs lacking a valid bearer.
      PATH:  TestClient -> HostValidator (Host=127.0.0.1:8765, pass)
             -> OriginCheckMiddleware (POST, no bearer, Origin=evil) -> 403.
      CHECK: status == 403 AND body == "Forbidden: invalid Origin".
      MUTATION: (a) Removing the ``app.add_middleware(OriginCheckMiddleware,
                ...)`` call would let the request reach the route, which
                returns 401 (invalid password) or 422. Either fails the 403
                check. (b) Body-text check pins the rejecter to the Origin
                middleware specifically, distinguishing it from a hypothetical
                401/403 from the route or the Host middleware ("Invalid host
                header").
      ESCAPE: A middleware that 403s every POST unconditionally would pass
              this test, but ``test_admin_app_allows_bearer_post_without_origin``
              below fails for it.
      IMPACT: A missing wiring lets cross-origin browsers POST to the admin
              API (CSRF), which is the whole defense being added in this PR.
    """
    from spellbook.admin.app import create_admin_app

    app = create_admin_app()
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"password": "irrelevant"},
        headers={
            "Host": "127.0.0.1:8765",
            "Origin": "http://evil.com",
        },
    )

    assert response.status_code == 403
    assert response.text == "Forbidden: invalid Origin"


def test_admin_app_allows_same_origin_post():
    """Task 5 contract: A POST whose ``Origin`` exactly matches an entry in
    ``app.state.allowed_origins`` (here ``http://127.0.0.1:8765``) passes
    the Origin check and reaches the route. The route then enforces its own
    auth (here the password is wrong so it returns 401), which is fine --
    we only assert the Origin layer did NOT reject with 403, and crucially
    that the body is NOT the Origin-rejection body.

    ESCAPE: test_admin_app_allows_same_origin_post
      CLAIM: A same-origin POST is not rejected by OriginCheckMiddleware
             and is allowed through to the route handler.
      PATH:  TestClient -> HostValidator (Host=127.0.0.1:8765, pass)
             -> OriginCheckMiddleware (POST, Origin matches allowlist) -> route
             -> route returns 401 ("Invalid password") because the password
             in the body doesn't match the mocked MCP token.
      CHECK: status != 403 AND body != "Forbidden: invalid Origin".
             Status is 401 specifically (route's invalid-password response).
      MUTATION: (a) An OriginCheck that rejects every POST regardless of
                Origin would 403 here -- both checks fail. (b) Missing
                ``app.state.allowed_origins`` plumbing (empty list) would
                cause all Origins to mismatch -> 403. (c) Order swap
                (Origin outer, Host inner) doesn't fail THIS test directly
                but is pinned by the cross-origin test above.
      ESCAPE: A middleware stack that passed everything through (no Origin
              check at all) would also reach the route and 401, passing this
              test. The cross-origin test above is the partner that rules
              that out.
      IMPACT: If same-origin POSTs were blocked, the admin UI's own forms
              (login, etc.) would all fail.
    """
    from spellbook.admin.app import create_admin_app

    app = create_admin_app()
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"password": "irrelevant"},
        headers={
            "Host": "127.0.0.1:8765",
            "Origin": "http://127.0.0.1:8765",
        },
    )

    assert response.status_code == 401
    assert response.text != "Forbidden: invalid Origin"


def test_admin_app_allows_bearer_post_without_origin(monkeypatch):
    """Task 5 contract: A POST presenting a valid Bearer token bypasses the
    Origin check even with no ``Origin`` header. The middleware resolves
    ``spellbook.admin.auth.load_token`` at request time, so the
    ``mock_mcp_token`` autouse fixture (which monkeypatches that symbol)
    determines the expected token; we re-read it here to construct the
    Authorization header.

    The route's invalid-password 401 is the expected reach -- we only assert
    the Origin layer let the request through (status != 403 AND body !=
    Origin rejection body).

    ESCAPE: test_admin_app_allows_bearer_post_without_origin
      CLAIM: Valid-bearer requests bypass OriginCheckMiddleware regardless
             of Origin presence.
      PATH:  TestClient -> HostValidator (Host=127.0.0.1:8765, pass)
             -> OriginCheckMiddleware (POST, valid bearer -> exempt) -> route
             -> 401 (invalid password).
      CHECK: status == 401 AND body != "Forbidden: invalid Origin".
      MUTATION: (a) Removing the bearer-exemption branch from
                OriginCheckMiddleware would 403 this request (no Origin
                header). (b) Wiring the middleware with the wrong
                allowed_origins (and removing bearer exemption) would 403.
                (c) Comparing the bearer with the wrong load_token reference
                would 403.
      ESCAPE: A middleware stack with NO OriginCheck at all would also pass
              this test, but the cross-origin rejection test above pins
              that down.
      IMPACT: Without bearer exemption, CLI tools using Bearer auth (which
              never send an Origin header) would be blocked from mutating
              endpoints.
    """
    import secrets as _secrets

    from spellbook.admin import auth as admin_auth
    from spellbook.admin.app import create_admin_app

    # Pin the token so we know what to put in the Authorization header.
    # The conftest autouse fixture also monkeypatches this; we override
    # both sites so the route's own load_token import and the middleware's
    # late-binding import see the same value.
    token = _secrets.token_urlsafe(32)
    monkeypatch.setattr(admin_auth, "load_token", lambda: token)
    monkeypatch.setattr(
        "spellbook.admin.routes.auth.load_token", lambda: token
    )

    app = create_admin_app()
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"password": "wrong-password"},
        headers={
            "Host": "127.0.0.1:8765",
            "Authorization": f"Bearer {token}",
        },
    )

    # Origin layer let it through (no 403, no Origin rejection body).
    # Route then returned 401 because the JSON password is "wrong-password",
    # not the bearer token value.
    assert response.status_code == 401
    assert response.text != "Forbidden: invalid Origin"


def test_admin_app_creates():
    from spellbook.admin.app import create_admin_app

    app = create_admin_app()
    assert app is not None
    assert app.title == "Spellbook Admin"


def test_admin_app_state_has_bound_port_and_origins():
    """Task 3 contract: ``create_admin_app()`` captures the bound port from
    ``get_env("PORT", "8765")`` (the same alias the CLI uses, which resolves
    to ``SPELLBOOK_MCP_PORT``) and stores it on ``app.state.bound_port``,
    along with the three-entry ``app.state.allowed_origins`` list used by
    the Origin middleware and WS handler.

    With no ``SPELLBOOK_MCP_PORT`` / ``PORT`` set the default is 8765, so
    the three origins are the loopback IPv4, loopback DNS, and bracketed
    loopback IPv6 forms at that port.
    """
    from spellbook.admin.app import create_admin_app

    app = create_admin_app()

    assert app.state.bound_port == 8765
    assert app.state.allowed_origins == [
        "http://127.0.0.1:8765",
        "http://localhost:8765",
        "http://[::1]:8765",
    ]


def test_admin_app_host_validator_runs_before_origin_check():
    """Pin middleware execution order: Host outermost, Origin inner.

    A request with BOTH a bad Host AND a bad Origin should be rejected by
    the Host middleware (status 400, body "Invalid host header"), NOT by
    the Origin middleware (status 403, body "Forbidden: invalid Origin").

    Catches regression: if the middleware add-order were inverted (Origin
    added after Host, making Origin outermost), the request would hit the
    Origin layer first and we'd see the 403 body instead of the 400 body.

    ESCAPE: test_admin_app_host_validator_runs_before_origin_check
      CLAIM: HostValidatorMiddleware runs strictly before OriginCheckMiddleware.
      PATH:  TestClient -> HostValidator (Host=evil.com, NOT in allowlist) ->
             400 "Invalid host header". Origin middleware is never reached.
      CHECK: status == 400 AND body exactly "Invalid host header".
      MUTATION:
        - Swapping the add_middleware order in create_admin_app (Origin then
          Host) would make Origin the outermost layer; Origin would see the
          bad Origin header and 403 with body "Forbidden: invalid Origin".
          Both the status and body assertions would fail.
        - Removing the Host middleware entirely would let the request reach
          Origin and 403 -- same failure mode.
        - Changing the Host rejection body string would also fail the
          body assertion, pinning the exact rejection text.
      ESCAPE: A stack that rejected EVERY request with 400 "Invalid host
              header" would pass this, but the same-origin and bearer
              passthrough tests above would fail for it.
      IMPACT: Order inversion would expose the Origin layer to malicious
              Host headers, defeating the DNS-rebinding defense's intent
              (the Host check should fire first; Origin is a separate
              CSRF defense for browser-origin requests).
    """
    from spellbook.admin.app import create_admin_app

    app = create_admin_app()
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        headers={"Host": "evil.com", "Origin": "http://evil.com"},
        json={"password": "anything"},
    )

    assert response.status_code == 400
    assert response.text == "Invalid host header"


def test_admin_app_rejects_bad_host():
    """Task 3 contract: ``HostValidatorMiddleware`` is wired into the admin
    app with the bare-hostname allowlist ``["127.0.0.1", "localhost", "::1"]``.

    A request with ``Host: evil.com`` must be rejected with HTTP 400 and the
    plain-text body ``"Invalid host header"`` produced by the middleware.
    """
    from spellbook.admin.app import create_admin_app

    app = create_admin_app()
    client = TestClient(app)

    response = client.get("/api/health", headers={"Host": "evil.com"})

    assert response.status_code == 400
    assert response.text == "Invalid host header"


def _task_names_running() -> set[str]:
    """Return the set of ``Task.get_name()`` values for currently-running
    tasks on the running loop. Filters out done/cancelled tasks so the
    assertion isn't flaky against tasks that have already exited."""
    return {t.get_name() for t in asyncio.all_tasks() if not t.done()}


async def test_lifespan_spawns_and_cancels_observability_tasks(monkeypatch):
    """Step 11 contract: the admin app lifespan registers both the
    ``purge_loop`` and ``threshold_eval_loop`` coroutines as background
    tasks on startup, and cancels/awaits them on shutdown.

    Why we patch the loops: the real ``purge_loop`` + ``threshold_eval_loop``
    read config and perform DB work. This test asserts the LIFESPAN
    WIRING (that the admin app creates the tasks and tears them down
    cleanly), so we stub the loop bodies with sleeps. Patching the
    ``spellbook.admin.app`` module attribute is load-bearing: ``_lifespan``
    resolves ``purge_loop`` / ``threshold_eval_loop`` via module globals
    at call time, so the monkeypatch IS the version the tasks run.

    Why we drive the lifespan directly (not via ``TestClient`` /
    ``httpx.ASGITransport``): FastAPI's ``TestClient`` runs the lifespan
    on a background thread with its own event loop, which makes
    cross-task ``asyncio.Event`` synchronization unreliable; httpx 0.28
    ``ASGITransport`` doesn't drive lifespan events at all. Calling
    ``app.router.lifespan_context(app)`` directly runs the real lifespan
    on the test's own event loop — exactly the surface we want to
    assert on.
    """
    import spellbook.admin.app as admin_app_mod

    purge_started = asyncio.Event()
    eval_started = asyncio.Event()
    purge_cancelled = asyncio.Event()
    eval_cancelled = asyncio.Event()

    async def fake_purge_loop() -> None:
        purge_started.set()
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            purge_cancelled.set()
            raise

    async def fake_threshold_eval_loop() -> None:
        eval_started.set()
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            eval_cancelled.set()
            raise

    monkeypatch.setattr(admin_app_mod, "purge_loop", fake_purge_loop)
    monkeypatch.setattr(
        admin_app_mod, "threshold_eval_loop", fake_threshold_eval_loop
    )

    app = admin_app_mod.create_admin_app()

    async with app.router.lifespan_context(app):
        # Yield once so the scheduler registers the newly-created tasks.
        # Without this yield the names are not yet present in
        # ``asyncio.all_tasks()``. Do NOT delete this sleep.
        await asyncio.sleep(0)

        # Both stubbed bodies must actually run — proves the tasks were
        # not just wrapped but also scheduled.
        await asyncio.wait_for(purge_started.wait(), timeout=1.0)
        await asyncio.wait_for(eval_started.wait(), timeout=1.0)

        names = _task_names_running()
        assert "spellbook-worker-llm-purge" in names, names
        assert "spellbook-worker-llm-threshold-eval" in names, names

    # Lifespan exit has completed — both task bodies must have seen a
    # CancelledError (i.e. were explicitly cancelled, not just abandoned).
    assert purge_cancelled.is_set()
    assert eval_cancelled.is_set()

    # And the named tasks must no longer appear in the running set.
    names_after = _task_names_running()
    assert "spellbook-worker-llm-purge" not in names_after, names_after
    assert (
        "spellbook-worker-llm-threshold-eval" not in names_after
    ), names_after


async def test_lifespan_cancel_during_first_tick_is_safe():
    """Cancel-during-batch safety probe (plan review I.8 / Step 9).

    Enter the lifespan, yield once, then immediately exit. The REAL
    ``purge_loop`` + ``threshold_eval_loop`` must handle the cancel
    gracefully: (a) the lifespan exits without a propagated exception
    and (b) the spellbook DB remains queryable afterwards (no leaked
    writer lock held by a stuck purge batch).
    """
    from sqlalchemy import select

    from spellbook.admin.app import create_admin_app
    from spellbook.db.engines import get_spellbook_sync_session
    from spellbook.db.spellbook_models import WorkerLLMCall

    app = create_admin_app()

    async with app.router.lifespan_context(app):
        await asyncio.sleep(0)  # yield so tasks register and run first line
    # Reaching this line without an exception proves the shutdown path
    # (cancel + await) completed cleanly for both real loops.

    # DB is queryable post-shutdown. We don't care about the rows, only
    # that the SELECT completes — a stuck writer lock would hang here.
    with get_spellbook_sync_session() as s:
        s.execute(select(WorkerLLMCall).limit(1)).all()
