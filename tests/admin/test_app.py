import asyncio


def test_admin_app_creates():
    from spellbook.admin.app import create_admin_app

    app = create_admin_app()
    assert app is not None
    assert app.title == "Spellbook Admin"


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
