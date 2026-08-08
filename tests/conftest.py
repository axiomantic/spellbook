"""Pytest configuration for spellbook tests."""

import hashlib
import os
import sys
from pathlib import Path

import pytest

# Resolved at conftest import, before any test can redirect ``HOME``. This is
# the developer's (or CI user's) genuine config file -- the one no test is ever
# allowed to touch.
REAL_USER_CONFIG_PATH = Path(os.path.expanduser("~")) / ".config" / "spellbook" / "spellbook.json"


def _real_user_config_fingerprint() -> tuple:
    """(exists, sha256, mtime_ns, size) of the real user config file.

    Absent file is a valid state and fingerprints as such, so a test that
    *creates* the real config is caught just as loudly as one that edits it.
    """
    try:
        raw = REAL_USER_CONFIG_PATH.read_bytes()
        st = REAL_USER_CONFIG_PATH.stat()
    except FileNotFoundError:
        return (False, None, None, None)
    except OSError:
        return (False, None, None, None)
    return (True, hashlib.sha256(raw).hexdigest(), st.st_mtime_ns, st.st_size)


_REAL_CONFIG_GUARD_MESSAGE = (
    "TEST ISOLATION FAILURE: the real user config at {path} was modified during "
    "the test run.\n"
    "  before: {before}\n"
    "  after:  {after}\n\n"
    "``spellbook.core.compat.get_config_dir`` resolves ``Path.home()/.config/spellbook`` "
    "and does NOT consult $SPELLBOOK_CONFIG_DIR. Setting that env var therefore isolates "
    "nothing for anything routed through ``spellbook.core.config`` (config_get, config_set, "
    "config_set_many, config_is_explicitly_set, get_config_path).\n"
    "Fix: redirect HOME instead -- ``monkeypatch.setenv(\"HOME\", str(tmp_path))``."
)


@pytest.fixture(scope="session", autouse=True)
def _guard_real_user_config_session():
    """Backstop: catch real-config writes from session fixtures or collection.

    The per-test guard below attributes pollution to a specific test. This one
    covers everything that happens outside a test body.
    """
    before = _real_user_config_fingerprint()
    yield
    after = _real_user_config_fingerprint()
    if before != after:
        raise AssertionError(
            _REAL_CONFIG_GUARD_MESSAGE.format(
                path=REAL_USER_CONFIG_PATH, before=before, after=after
            )
        )


@pytest.fixture(autouse=True)
def _guard_real_user_config(request):
    """Fail the offending test if it mutates the developer's real config file.

    Function-scoped so the failure names the exact test rather than surfacing
    at session teardown with no attribution. The file is small; two reads per
    test is a negligible cost for closing a defect that already wrote 14 stray
    ``rules.module.*`` keys into a real user's ``spellbook.json``.

    Tests that deliberately exercise this guard mark themselves
    ``allow_real_config_write`` and opt out.
    """
    if request.node.get_closest_marker("allow_real_config_write"):
        yield
        return
    before = _real_user_config_fingerprint()
    yield
    after = _real_user_config_fingerprint()
    if before != after:
        raise AssertionError(
            _REAL_CONFIG_GUARD_MESSAGE.format(
                path=REAL_USER_CONFIG_PATH, before=before, after=after
            )
        )


@pytest.fixture(autouse=True)
def _force_gates_enabled(request, monkeypatch):
    """Neutralize the operator gate kill switch during test runs.

    ``hooks.spellbook_hook._gates_disabled`` honors a host-level
    ``~/.local/spellbook/gates-disabled`` flag file (and the
    ``SPELLBOOK_GATES_DISABLED`` env var). Test runs must not depend on the
    developer's local kill-switch state, so pin the gates ON by default via
    the authoritative env var — this also propagates into the hook
    subprocesses spawned by ``_run_hook`` (which inherit ``os.environ``).

    Tests that exercise the kill switch itself mark themselves
    ``gate_killswitch`` and opt out, controlling the env var / flag file
    directly.
    """
    if request.node.get_closest_marker("gate_killswitch"):
        return
    monkeypatch.setenv("SPELLBOOK_GATES_DISABLED", "0")


@pytest.fixture(scope="session", autouse=True)
def _ensure_worker_llm_calls_table():
    """Create the ``worker_llm_calls`` table on the real spellbook.db.

    CI runs against a fresh ``~/.local/spellbook/spellbook.db`` with no
    Alembic migrations applied. Any test that enters a code path which
    calls ``spellbook.worker_llm.observability.record_call`` (e.g. via
    ``publish_call`` with ``_in_daemon=True``) hits an
    ``OperationalError: no such table: worker_llm_calls``. ``record_call``
    swallows the error but logs a WARNING on its first-per-process
    failure, which tripwire's autouse ``LogPlugin`` captures. Without an
    assertion on that log, sandbox teardown raises
    ``UnassertedInteractionsError`` and the test fails.

    This fixture creates ONLY ``worker_llm_calls`` on the sync engine
    that ``record_call`` uses (``get_spellbook_sync_session`` ->
    ``_get_or_create_sync_engine(DB_DIR / "spellbook.db")``). Other
    spellbook tables and the fractal/forged/coordination DBs are left
    untouched. ``checkfirst=True`` makes this a no-op when the table
    already exists (e.g. local dev DBs where Alembic has run).
    """
    try:
        from spellbook.db.engines import DB_DIR, _get_or_create_sync_engine
        from spellbook.db.spellbook_models import WorkerLLMCall
    except ImportError:
        # Some bootstrap test runs import conftest before spellbook is
        # importable. Missing import here is benign — those runs never
        # reach ``record_call``.
        return

    engine = _get_or_create_sync_engine(str(DB_DIR / "spellbook.db"))
    WorkerLLMCall.__table__.create(engine, checkfirst=True)


@pytest.fixture(scope="session", autouse=True)
def _ensure_hook_events_table():
    """Create the ``hook_events`` table on the real spellbook.db.

    Mirrors ``_ensure_worker_llm_calls_table``: CI runs against a fresh
    ``~/.local/spellbook/spellbook.db`` with no Alembic migrations applied.
    Any test that enters a code path which calls
    ``spellbook.hooks.observability.record_hook_event`` hits an
    ``OperationalError: no such table: hook_events``. ``record_hook_event``
    swallows the error but logs a WARNING on its first-per-process
    failure, which tripwire's autouse ``LogPlugin`` captures.

    ``checkfirst=True`` makes this a no-op when the table already exists.
    """
    try:
        from spellbook.db.engines import DB_DIR, _get_or_create_sync_engine
        from spellbook.db.spellbook_models import HookEvent
    except ImportError:
        return

    engine = _get_or_create_sync_engine(str(DB_DIR / "spellbook.db"))
    HookEvent.__table__.create(engine, checkfirst=True)


@pytest.fixture(autouse=True)
def _isolate_worker_llm_config_from_user(monkeypatch):
    """Force worker_llm_* config keys to return None by default.

    Several test suites (tests/test_worker_llm/, tests/test_hooks/) exercise
    code paths that read ``spellbook.core.config.config_get("worker_llm_*")``
    and expect the default "feature off" state. Without isolation those reads
    fall through to the developer's real ``spellbook.json``, which on machines
    with the worker LLM configured returns ``feature_tool_safety: True`` and
    flips backwards-compat invariants from feature-off to feature-on, causing
    spurious failures and real HTTP attempts.

    This fixture wraps ``config_get`` so any key starting with ``worker_llm_``
    returns ``None`` (callers apply their own defaults). All other keys pass
    through to the real implementation so session_init/profile/notify/etc.
    keep working.

    Tests that explicitly want worker_llm features on (``worker_llm_config``
    fixture in the worker_llm suite) override this patch with their own
    ``monkeypatch.setattr`` call on the same attribute.
    """
    try:
        from spellbook.core import config as _cfg
    except ImportError:
        return  # spellbook not importable in some bootstrap tests; no-op

    real_config_get = _cfg.config_get

    def isolated(key):
        if isinstance(key, str) and key.startswith("worker_llm_"):
            return None
        return real_config_get(key)

    monkeypatch.setattr(_cfg, "config_get", isolated)

    # ``spellbook.worker_llm.config`` did ``from spellbook.core.config import
    # config_get`` at module load, so its local name must be patched too.
    try:
        from spellbook.worker_llm import config as _wl_cfg
        monkeypatch.setattr(_wl_cfg, "config_get", isolated)
    except ImportError:
        pass


# On Windows, use SelectorEventLoop to avoid ProactorEventLoop issues:
# - aiosqlite is incompatible with ProactorEventLoop
# - ProactorEventLoop.close() hangs on teardown (GetQueuedCompletionStatus)
# - TestClient (anyio) interactions fail with ProactorEventLoop
if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add project root to path so spellbook can be imported
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def get_tool_fn(tool):
    """Get the callable function from a FastMCP tool, compatible with both v2 and v3.

    In FastMCP v2, @mcp.tool() returns a FunctionTool object with a .fn attribute.
    In FastMCP v3, @mcp.tool() returns the original function directly.
    """
    return getattr(tool, "fn", tool)


def pytest_addoption(parser):
    parser.addoption(
        "--run-docker",
        action="store_true",
        default=False,
        help="Run docker-marked tests (skipped by default, intended for CI)",
    )


def _current_platform() -> str:
    """Return the current ``sys.platform``.

    Indirection so tests can redirect the platform probe (see ``tests/installer/test_marks.py``)
    via ``tripwire.mock("tests.conftest:_current_platform")`` instead of patching
    the module-level ``sys.platform`` attribute.
    """
    return sys.platform


def pytest_collection_modifyitems(config, items):
    skip_docker = pytest.mark.skip(reason="docker tests only run in CI (use --run-docker)")
    skip_posix_only = pytest.mark.skip(reason="POSIX only")
    skip_windows_only = pytest.mark.skip(reason="Windows only")
    run_docker = config.getoption("--run-docker")
    is_windows = _current_platform().startswith("win")

    for item in items:
        if not run_docker and "docker" in item.keywords:
            item.add_marker(skip_docker)
        if "windows_only" in item.keywords and not is_windows:
            item.add_marker(skip_windows_only)
        if "posix_only" in item.keywords and is_windows:
            item.add_marker(skip_posix_only)
