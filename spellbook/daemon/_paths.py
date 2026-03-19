"""Internal path helpers shared across daemon submodules.

These are private to the daemon package; external callers should use
the public APIs in manager, pid, and service.
"""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

from spellbook.core.config import get_spellbook_dir  # noqa: F401 (re-export)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8765
DEFAULT_HOST = "127.0.0.1"
SERVICE_NAME = "spellbook-mcp"
LAUNCHD_LABEL = "com.spellbook.mcp"


# ---------------------------------------------------------------------------
# Config / log / pid paths
# ---------------------------------------------------------------------------


def get_config_dir() -> Path:
    """Get the spellbook config directory."""
    config_dir = Path(
        os.environ.get("SPELLBOOK_CONFIG_DIR", Path.home() / ".local" / "spellbook")
    )
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_pid_file() -> Path:
    """Get path to the daemon PID file."""
    return get_config_dir() / f"{SERVICE_NAME}.pid"


def get_log_file() -> Path:
    """Get path to the daemon stdout log."""
    return get_config_dir() / f"{SERVICE_NAME}.log"


def get_err_log_file() -> Path:
    """Get path to the daemon stderr log."""
    return get_config_dir() / f"{SERVICE_NAME}.err.log"


# ---------------------------------------------------------------------------
# Host / port / URL helpers
# ---------------------------------------------------------------------------


def get_port() -> int:
    """Get the configured MCP port (default 8765)."""
    return int(os.environ.get("SPELLBOOK_MCP_PORT", DEFAULT_PORT))


def get_host() -> str:
    """Get the configured MCP host (default 127.0.0.1)."""
    return os.environ.get("SPELLBOOK_MCP_HOST", DEFAULT_HOST)


def get_server_url() -> str:
    """Get the full MCP server URL."""
    return f"http://{get_host()}:{get_port()}/mcp"


def get_platform() -> str:
    """Get the current platform: 'darwin', 'linux', or 'windows'."""
    return platform.system().lower()


# ---------------------------------------------------------------------------
# Server script / Python helpers
# ---------------------------------------------------------------------------


def get_server_script() -> Path:
    """Get path to the server script."""
    return get_spellbook_dir() / "spellbook_mcp" / "server.py"


def get_uv_path() -> str | None:
    """Get path to uv, or None if not installed."""
    return shutil.which("uv")


def get_daemon_python() -> str | None:
    """Get path to daemon venv Python, or None if not available.

    The installer sets SPELLBOOK_DAEMON_PYTHON to the absolute path of the
    Python interpreter inside the daemon's isolated venv
    (~/.local/spellbook/daemon-venv/).  We use it directly in service files
    so the daemon doesn't depend on ``uv`` at runtime.
    """
    path = os.environ.get("SPELLBOOK_DAEMON_PYTHON")
    if path and Path(path).is_file():
        # Do NOT resolve() -- the venv Python must stay as-is so that
        # Python activates the venv site-packages based on the interpreter
        # path being inside the venv directory.  Resolving follows the
        # symlink to the underlying system Python which has no packages.
        return str(Path(path).absolute())
    return None
