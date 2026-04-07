"""TTS venv creation and management.

Creates and manages a dedicated Python venv for wyoming-kokoro-torch
at ~/.local/spellbook/tts-venv/. Separate from the daemon venv to
avoid bloating it with PyTorch (~2GB).
"""

import asyncio
import logging
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional

from spellbook.tts.constants import TTS_MIN_DISK_SPACE_BYTES

logger = logging.getLogger(__name__)


def get_tts_venv_dir() -> Path:
    """Return path to TTS-dedicated venv."""
    return Path.home() / ".local" / "spellbook" / "tts-venv"


def get_tts_data_dir() -> Path:
    """Return path to TTS model data directory."""
    return Path.home() / ".local" / "spellbook" / "tts-data"


def get_tts_python(tts_venv_dir: Path) -> Path:
    """Return path to Python interpreter in TTS venv.

    Args:
        tts_venv_dir: TTS venv root directory.

    Returns:
        Path to the Python executable.
    """
    if sys.platform == "win32":
        return tts_venv_dir / "Scripts" / "python.exe"
    return tts_venv_dir / "bin" / "python"


async def create_tts_venv(
    tts_venv_dir: Path,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> tuple[bool, str]:
    """Create TTS venv and install wyoming-kokoro-torch.

    Async: runs subprocess calls via asyncio to avoid blocking the event
    loop during lazy provisioning from the MCP daemon.

    Args:
        tts_venv_dir: Target venv directory.
        progress_callback: Optional (stage_name, fraction) reporter.

    Returns:
        (success, message) tuple.
    """
    def _report(stage: str, pct: float) -> None:
        if progress_callback:
            progress_callback(stage, pct)

    # Check disk space
    parent = tts_venv_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(str(parent))
    if usage.free < TTS_MIN_DISK_SPACE_BYTES:
        free_gb = usage.free / (1024**3)
        return (
            False,
            f"Insufficient disk space: {free_gb:.1f}GB free, "
            f"need {TTS_MIN_DISK_SPACE_BYTES / (1024**3):.0f}GB",
        )

    _report("Creating TTS venv", 0.1)

    # Create venv using current interpreter's major.minor version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    try:
        proc = await asyncio.create_subprocess_exec(
            "uv", "venv", str(tts_venv_dir), "--python", python_version, "--seed",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            return (False, f"Failed to create TTS venv: {stderr.decode().strip()}")
    except FileNotFoundError:
        return (False, "uv not found; cannot create TTS venv")

    _report("Installing wyoming-kokoro-torch", 0.3)

    # Install wyoming-kokoro-torch
    tts_python = get_tts_python(tts_venv_dir)
    try:
        proc = await asyncio.create_subprocess_exec(
            "uv", "pip", "install",
            "--python", str(tts_python),
            "wyoming-kokoro-torch>=3.0.0",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            return (
                False,
                f"Failed to install wyoming-kokoro-torch: {stderr.decode().strip()}",
            )
    except FileNotFoundError:
        return (False, "uv not found; cannot install TTS deps")

    _report("TTS venv ready", 1.0)
    return (True, "TTS venv created and wyoming-kokoro-torch installed")
