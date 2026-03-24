"""Backward compatibility shim. Use spellbook.mcp.server and spellbook.mcp.tools instead.

This module re-exports symbols from their new locations so that existing
imports continue to work. New code should import directly from:
  - spellbook.mcp.server (mcp instance, build_http_run_kwargs, etc.)
  - spellbook.mcp.tools.* (individual tool functions)
"""
# ruff: noqa: F401,F403,E402

# Server core
from spellbook.mcp.server import (  # noqa: F401
    mcp,
    _FASTMCP_MAJOR,
    build_http_run_kwargs,
    startup,
    shutdown,
)

# Re-export all tool functions for backward compatibility
from spellbook.mcp.tools.misc import *  # noqa: F401,F403
from spellbook.mcp.tools.sessions import *  # noqa: F401,F403
from spellbook.mcp.tools.security import *  # noqa: F401,F403
from spellbook.mcp.tools.forged import *  # noqa: F401,F403
from spellbook.mcp.tools.updates import *  # noqa: F401,F403
from spellbook.mcp.tools.health import *  # noqa: F401,F403
from spellbook.mcp.tools.config import *  # noqa: F401,F403
from spellbook.mcp.tools.coordination import *  # noqa: F401,F403
from spellbook.mcp.tools.experiments import *  # noqa: F401,F403
from spellbook.mcp.tools.fractal import *  # noqa: F401,F403
from spellbook.mcp.tools.memory import *  # noqa: F401,F403
from spellbook.mcp.tools.notifications import *  # noqa: F401,F403
from spellbook.mcp.tools.pr import *  # noqa: F401,F403

# Domain functions expected by integration tests
from spellbook.fractal.schema import init_fractal_schema  # noqa: F401
from spellbook.forged.schema import init_forged_schema  # noqa: F401
from spellbook.coordination.curator import init_curator_tables  # noqa: F401

# Private names not covered by wildcard imports but used by tests
from spellbook.mcp.tools.misc import _deep_merge  # noqa: F401
from spellbook.mcp.tools.sessions import _validate_working_directory  # noqa: F401
from spellbook.mcp.tools.forged import _extract_section  # noqa: F401
from spellbook.mcp.tools.health import get_tool_names, _get_version  # noqa: F401
_get_tool_names = get_tool_names  # backward compat for tests importing old name

# Function aliases for backward compat
_shutdown_cleanup = shutdown

# State variable proxying for backward compat.
# Old code accessed server._first_health_check_done etc. as module attributes.
# These now live in spellbook.mcp.state. We proxy via __getattr__/__setattr__.
import spellbook.mcp.state as _mcp_state  # noqa: E402

_STATE_ATTRS = {
    "_first_health_check_done": "first_health_check_done",
    "_last_full_health_check_time": "last_full_health_check_time",
    "_server_start_time": "server_start_time",
    "FULL_HEALTH_CHECK_INTERVAL_SECONDS": "FULL_HEALTH_CHECK_INTERVAL_SECONDS",
    "_watcher": "watcher",
    "_update_watcher": "update_watcher",
}


def __getattr__(name):
    state_attr = _STATE_ATTRS.get(name)
    if state_attr is not None:
        return getattr(_mcp_state, state_attr)
    raise AttributeError(f"module 'spellbook.server' has no attribute {name!r}")


import sys as _sys  # noqa: E402

class _ServerModule(_sys.modules[__name__].__class__):
    """Module subclass that supports __setattr__ for state proxying."""
    def __setattr__(self, name, value):
        state_attr = _STATE_ATTRS.get(name)
        if state_attr is not None:
            setattr(_mcp_state, state_attr, value)
            return
        super().__setattr__(name, value)

_sys.modules[__name__].__class__ = _ServerModule
