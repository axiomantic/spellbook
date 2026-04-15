"""Pytest configuration for spellbook tests."""

import shutil
import sys
import warnings
from pathlib import Path

import pytest


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
