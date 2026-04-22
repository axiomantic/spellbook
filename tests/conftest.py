"""Pytest configuration for spellbook tests."""

import shutil
import sys
import warnings
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _ensure_worker_llm_calls_table():
    """Create the ``worker_llm_calls`` table on the real spellbook.db.

    CI runs against a fresh ``~/.local/spellbook/spellbook.db`` with no
    Alembic migrations applied. Any test that enters a code path which
    calls ``spellbook.worker_llm.observability.record_call`` (e.g. via
    ``publish_call`` with ``_in_daemon=True``) hits an
    ``OperationalError: no such table: worker_llm_calls``. ``record_call``
    swallows the error but logs a WARNING on its first-per-process
    failure, which bigfoot's autouse ``LogPlugin`` captures. Without an
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


def _memory_tools_installed() -> bool:
    return bool(shutil.which("qmd")) and bool(shutil.which("serena"))

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


def pytest_collection_modifyitems(config, items):
    memory_tools_ok = _memory_tools_installed()
    skip_memory = pytest.mark.skip(
        reason="QMD and Serena required for memory system tests"
    )
    skip_docker = pytest.mark.skip(reason="docker tests only run in CI (use --run-docker)")
    run_docker = config.getoption("--run-docker")

    skipped_memory_count = 0
    for item in items:
        if not memory_tools_ok and "requires_memory_tools" in item.keywords:
            item.add_marker(skip_memory)
            skipped_memory_count += 1
        if not run_docker and "docker" in item.keywords:
            item.add_marker(skip_docker)

    if skipped_memory_count > 0:
        # Loud warning so the skip is impossible to miss in the terminal
        # output. See AGENTS.spellbook.md -> "Test dependency exceptions".
        warnings.warn(
            f"{skipped_memory_count} tests skipped: QMD/Serena not installed. "
            f"See AGENTS.spellbook.md for rationale.",
            category=UserWarning,
            stacklevel=1,
        )
        terminal = config.pluginmanager.get_plugin("terminalreporter")
        if terminal is not None:
            terminal.write_line("")
            terminal.write_line(
                f"WARNING: {skipped_memory_count} tests skipped: "
                f"QMD/Serena not installed. "
                f"See AGENTS.spellbook.md for rationale.",
                yellow=True, bold=True,
            )
