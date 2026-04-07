"""TTS provisioning state machine.

Ensures TTS is fully provisioned: venv, deps, model, service.
Idempotent. Safe to call repeatedly. Uses cross-process lock.
"""

import asyncio
import logging
from pathlib import Path
from typing import Callable, Optional

from spellbook.core.config import config_get, config_set
from spellbook.core.services import ServiceManager, tts_service_config
from spellbook.tts.constants import (
    TTS_DEFAULT_PORT,
    TTS_DEFAULT_VOICE,
    TTS_HEALTH_PROBE_DELAYS_S,
)
from spellbook.tts.device import detect_device
from spellbook.tts.lock import ProvisioningLocked, provisioning_lock
from spellbook.tts.venv import create_tts_venv, get_tts_python, get_tts_venv_dir

logger = logging.getLogger(__name__)


async def _check_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is available (nothing listening).

    Args:
        port: Port number to check.
        host: Host to check against.

    Returns:
        True if the port is free, False if something is listening.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=1,
        )
        writer.close()
        await writer.wait_closed()
        return False  # Something is already listening
    except (OSError, asyncio.TimeoutError):
        return True  # Port is free


async def _health_probe(host: str, port: int) -> bool:
    """TCP health probe for the TTS server.

    Args:
        host: Server host.
        port: Server port.

    Returns:
        True if TCP connection succeeds.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=2,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def _progressive_health_check(host: str, port: int) -> bool:
    """Progressive health check with exponential backoff.

    Probes at 2s, 5s, 10s, 20s, 40s intervals (77s total).
    Returns True on first successful probe.

    Args:
        host: Server host.
        port: Server port.

    Returns:
        True if any probe succeeds within the schedule.
    """
    for delay in TTS_HEALTH_PROBE_DELAYS_S:
        await asyncio.sleep(delay)
        if await _health_probe(host, port):
            return True
    return False


async def ensure_provisioned(
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> dict:
    """Ensure TTS is fully provisioned: venv, deps, model, service.

    Idempotent. Safe to call repeatedly. Uses cross-process lock.

    Args:
        progress_callback: Optional (stage_name, fraction) reporter.

    Returns:
        {"status": "ok"|"error"|"already_provisioning",
         "detail": str,
         "steps_completed": list[str]}
    """
    steps_completed: list[str] = []

    def _report(stage: str, pct: float) -> None:
        if progress_callback:
            progress_callback(stage, pct)

    # Acquire provisioning lock (non-blocking).
    # The lock uses flock (Unix) / msvcrt (Windows) with LOCK_NB, so
    # acquisition is a single non-blocking syscall (microseconds of file
    # I/O). For truly async locking, asyncio.to_thread() could be used
    # but is unnecessary for this use case.
    try:
        with provisioning_lock():
            tts_venv_dir = get_tts_venv_dir()
            tts_python = get_tts_python(tts_venv_dir)

            # Verify filesystem state matches config
            deps_installed = config_get("tts_deps_installed")
            service_installed = config_get("tts_service_installed")

            if deps_installed and not tts_python.exists():
                logger.warning("tts_deps_installed=true but venv python missing; resetting")
                config_set("tts_deps_installed", False)
                config_set("tts_service_installed", False)
                deps_installed = False
                service_installed = False

            # Step 1: Install deps if needed
            if not deps_installed:
                _report("Installing TTS dependencies", 0.1)
                success, msg = await create_tts_venv(
                    tts_venv_dir, progress_callback=progress_callback,
                )
                if not success:
                    return {
                        "status": "error",
                        "detail": msg,
                        "steps_completed": steps_completed,
                    }
                config_set("tts_deps_installed", True)
                steps_completed.append("deps")

            # Step 2: Install and start service if needed
            #
            # Known limitation: if service_installed is already True, changes
            # to tts_voice or tts_device config won't take effect because the
            # service install step is skipped entirely.
            # Workaround: set tts_service_installed=false then re-provision
            # to pick up new voice/device settings.
            if not service_installed:
                _report("Configuring TTS service", 0.6)

                device = detect_device()
                port = config_get("tts_wyoming_port") or TTS_DEFAULT_PORT
                voice = config_get("tts_voice") or TTS_DEFAULT_VOICE

                # Check port availability
                if not await _check_port_available(port):
                    return {
                        "status": "error",
                        "detail": f"Port {port} is already in use. "
                        "Change tts_wyoming_port in config.",
                        "steps_completed": steps_completed,
                    }

                # Build ServiceConfig and install
                svc_config = tts_service_config(
                    tts_venv_dir=tts_venv_dir,
                    port=port,
                    device=device,
                    voice=voice,
                )
                manager = ServiceManager(svc_config)

                _report("Installing TTS service", 0.7)
                success, msg = manager.install()
                if not success:
                    return {
                        "status": "error",
                        "detail": f"Service install failed: {msg}",
                        "steps_completed": steps_completed,
                    }

                config_set("tts_service_installed", True)
                config_set("tts_device", device)
                steps_completed.append("service")

                # Progressive health check
                _report("Waiting for TTS service to start", 0.8)
                healthy = await _progressive_health_check("127.0.0.1", port)
                if healthy:
                    _report("TTS service healthy", 1.0)
                else:
                    logger.info(
                        "TTS service not yet responding after health check; "
                        "may be downloading model on first start"
                    )
                    _report("TTS service starting (model download may be in progress)", 0.9)
            else:
                # Service already installed; verify it's running
                port = config_get("tts_wyoming_port") or TTS_DEFAULT_PORT
                svc_config = tts_service_config(tts_venv_dir=tts_venv_dir, port=port)
                manager = ServiceManager(svc_config)

                # is_running() uses blocking socket I/O (max 2s timeout).
                # Acceptable here as the provisioner has no concurrent async
                # work at this point. For truly async health checks, see
                # _health_probe() / _progressive_health_check().
                if not manager.is_running():
                    _report("Starting TTS service", 0.8)
                    started, start_msg = manager.start()
                    if not started:
                        return {
                            "status": "error",
                            "detail": f"Service start failed: {start_msg}",
                            "steps_completed": steps_completed,
                        }
                    await _progressive_health_check("127.0.0.1", port)

            return {
                "status": "ok",
                "detail": "TTS fully provisioned",
                "steps_completed": steps_completed,
            }

    except ProvisioningLocked:
        return {
            "status": "already_provisioning",
            "detail": "Another process is provisioning TTS",
            "steps_completed": [],
        }
    except Exception as e:
        logger.exception("TTS provisioning failed")
        return {
            "status": "error",
            "detail": str(e),
            "steps_completed": steps_completed,
        }


def provision_sync(
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> dict:
    """Synchronous wrapper for ensure_provisioned.

    For use in the installer's synchronous context. MUST NOT be called
    from within an existing event loop.

    Args:
        progress_callback: Optional progress reporter.

    Returns:
        Same dict as ensure_provisioned().
    """
    return asyncio.run(ensure_provisioned(progress_callback=progress_callback))
