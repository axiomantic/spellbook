"""HTTP custom routes for the MCP server.

Registers REST endpoints via @mcp.custom_route() for use by hook scripts
and monitoring tools that need HTTP access without full MCP protocol.
"""

import asyncio
import logging
import time
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Project imports must follow logger setup so they pick up the configured logger.
from spellbook.core.path_utils import get_spellbook_config_dir  # noqa: E402
from spellbook.mcp import state as _state  # noqa: E402
from spellbook.mcp.server import mcp  # noqa: E402


def _get_version() -> str:
    """Read version from .version file."""
    import os
    from pathlib import Path

    try:
        version_path = Path(__file__).parent.parent.parent / ".version"
        if version_path.exists():
            return version_path.read_text(encoding="utf-8").strip()

        spellbook_dir = os.environ.get("SPELLBOOK_DIR")
        if spellbook_dir:
            version_path = Path(spellbook_dir) / ".version"
            if version_path.exists():
                return version_path.read_text(encoding="utf-8").strip()

        return "unknown"
    except OSError:
        return "unknown"


@mcp.custom_route("/health", methods=["GET"])
async def api_health(request: Request) -> JSONResponse:
    """Lightweight health check endpoint for the installer and monitoring.

    Returns JSON: {"status": "ok", "version": "...", "uptime_seconds": ...}
    """
    return JSONResponse({
        "status": "ok",
        "version": _get_version(),
        "uptime_seconds": round(time.time() - _state.server_start_time, 1),
    })


# ---------------------------------------------------------------------------
# Hook log rotation (moved from hooks/spellbook_hook.py)
# ---------------------------------------------------------------------------

_HOOK_LOG_MAX_BYTES = 1_000_000  # 1 MB
_HOOK_LOG_BACKUP_COUNT = 3
_hook_log_lock = asyncio.Lock()


def _rotate_hook_log(log_file: Path) -> None:
    """Rotate hook log file if it exceeds _HOOK_LOG_MAX_BYTES.

    Keeps up to _HOOK_LOG_BACKUP_COUNT backups: hook-errors.log.1, .2, .3.
    Must be called while holding _hook_log_lock.
    """
    try:
        if not log_file.exists() or log_file.stat().st_size < _HOOK_LOG_MAX_BYTES:
            return
        for i in range(_HOOK_LOG_BACKUP_COUNT, 0, -1):
            if i == _HOOK_LOG_BACKUP_COUNT:
                src = log_file.with_suffix(f".log.{i}")
                if src.exists():
                    src.unlink()
            else:
                src = log_file.with_suffix(f".log.{i}")
                dst = log_file.with_suffix(f".log.{i + 1}")
                if src.exists():
                    src.replace(dst)
        log_file.replace(log_file.with_suffix(".log.1"))
    except OSError:
        pass  # Best-effort rotation


@mcp.custom_route("/api/hook-log", methods=["POST"])
async def api_hook_log(request: Request) -> JSONResponse:
    """REST endpoint for hook scripts to log errors via the daemon.

    Accepts JSON body: {"timestamp": "ISO string", "event": "string", "traceback": "string"}
    Returns JSON: {"ok": true} on success.

    The daemon writes to ~/.local/spellbook/logs/hook-errors.log with
    rotation, eliminating the need for hook processes to have write access
    to the config directory.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    timestamp = body.get("timestamp", "")
    event = body.get("event", "")
    tb = body.get("traceback", "")

    if not event:
        return JSONResponse({"error": "missing required field: event"}, status_code=400)

    log_dir = get_spellbook_config_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "hook-errors.log"

    def _write_log(path: Path, text: str) -> None:
        _rotate_hook_log(path)
        with open(path, "a") as f:
            f.write(text)

    entry = f"\n{'=' * 60}\n{timestamp}\n{event}\n{tb}"
    async with _hook_log_lock:
        await asyncio.to_thread(_write_log, log_file, entry)

    return JSONResponse({"ok": True})


@mcp.custom_route("/api/hooks/record", methods=["POST"])
async def api_hooks_record(request: Request) -> JSONResponse:
    """Persist a hook dispatcher invocation into ``hook_events``.

    Subprocess hook scripts (``hooks/spellbook_hook.py`` etc.) have no
    running event loop, so they POST here and the daemon writes the row
    on their behalf.

    Accepts JSON body:
        {
          "hook_name": str,     # required; <=128 chars
          "event_name": str,    # required; <=128 chars
          "tool_name": str,     # optional; <=128 chars
          "duration_ms": int,   # required; >=0
          "exit_code": int,     # required
          "error": str,         # optional; <=1000 chars
          "notes": str          # optional; <=4000 chars
        }

    Returns:
        - 202 ``{"ok": true}`` when accepted.
        - 400 on missing/invalid fields.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    hook_name = body.get("hook_name")
    event_name = body.get("event_name")
    duration_ms = body.get("duration_ms")
    exit_code = body.get("exit_code")
    tool_name = body.get("tool_name")
    error = body.get("error")
    notes = body.get("notes")

    if not isinstance(hook_name, str) or not hook_name or len(hook_name) > 128:
        return JSONResponse(
            {"error": "missing or invalid 'hook_name' (1..128 chars)"},
            status_code=400,
        )
    if not isinstance(event_name, str) or not event_name or len(event_name) > 128:
        return JSONResponse(
            {"error": "missing or invalid 'event_name' (1..128 chars)"},
            status_code=400,
        )
    if tool_name is not None:
        if not isinstance(tool_name, str) or len(tool_name) > 128:
            return JSONResponse(
                {"error": "invalid 'tool_name' (<=128 chars or null)"},
                status_code=400,
            )
    if not isinstance(duration_ms, int) or isinstance(duration_ms, bool) or duration_ms < 0:
        return JSONResponse(
            {"error": "missing or invalid 'duration_ms' (non-negative int)"},
            status_code=400,
        )
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        return JSONResponse(
            {"error": "missing or invalid 'exit_code' (int)"},
            status_code=400,
        )
    if error is not None:
        if not isinstance(error, str) or len(error) > 1000:
            return JSONResponse(
                {"error": "invalid 'error' (<=1000 chars or null)"},
                status_code=400,
            )
    if notes is not None:
        if not isinstance(notes, str) or len(notes) > 4000:
            return JSONResponse(
                {"error": "invalid 'notes' (<=4000 chars or null)"},
                status_code=400,
            )

    try:
        from functools import partial

        from spellbook.hooks.observability import record_hook_event

        # ``record_hook_event`` runs a synchronous SQLite INSERT; calling
        # it directly from this async handler would hold the daemon event
        # loop for the duration of the write. Offload via
        # ``run_in_executor``.
        #
        # ``loop.run_in_executor(executor, func, *args)`` takes positional
        # args only. Passing kwargs directly raises TypeError and the
        # function never runs -- which means hook observability rows were
        # silently lost. Bind the kwargs with ``functools.partial`` so the
        # executor actually calls the function.
        import asyncio as _asyncio
        _asyncio.get_running_loop().run_in_executor(
            None,
            partial(
                record_hook_event,
                hook_name=hook_name,
                event_name=event_name,
                duration_ms=duration_ms,
                exit_code=exit_code,
                tool_name=tool_name,
                error=error,
                notes=notes,
            ),
        )
    except Exception:
        logger.debug(
            "api_hooks_record: failed to spawn record_hook_event",
            exc_info=True,
        )

    return JSONResponse({"ok": True}, status_code=202)
