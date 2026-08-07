"""Backward compatibility shim. Use spellbook.mcp.server instead."""

from spellbook.mcp.server import (  # noqa: F401
    mcp,
    _FASTMCP_MAJOR,
    build_http_run_kwargs,
    startup,
    shutdown,
)

# Function aliases for backward compat
_shutdown_cleanup = shutdown

# State proxying
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
