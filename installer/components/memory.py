"""Installer component: memory system dependencies (QMD, Serena).

Installs the hard dependencies for the spellbook memory system:
- QMD (hybrid search via BM25 + vector + re-ranking)
- Serena (code-intelligence for at-risk memory detection)

Both tools must be on PATH for the memory system to operate.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Dict


QMD_INSTALL_CMD = ["npm", "install", "-g", "@tobilu/qmd"]
SERENA_INSTALL_CMD = [
    "uv", "tool", "install",
    "-p", "3.13",
    "serena-agent@latest",
    "--prerelease=allow",
]


def is_qmd_installed() -> bool:
    """Return True if the qmd binary is on PATH."""
    return shutil.which("qmd") is not None


def is_serena_installed() -> bool:
    """Return True if the serena binary is on PATH."""
    return shutil.which("serena") is not None


def install_qmd() -> bool:
    """Install QMD globally via npm. Returns True on success."""
    try:
        proc = subprocess.run(
            QMD_INSTALL_CMD,
            capture_output=True,
            text=True,
            timeout=180,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def install_serena() -> bool:
    """Install Serena via uv tool. Returns True on success."""
    try:
        proc = subprocess.run(
            SERENA_INSTALL_CMD,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def setup_memory_system(enable: bool) -> Dict[str, bool]:
    """Configure the memory system.

    When enable is True, installs QMD and Serena (skipping installs
    for tools already on PATH). When enable is False, skips installs
    and only reports current availability.

    Returns:
        Dict with:
        - enabled: whether setup was requested
        - qmd: whether QMD is now available
        - serena: whether Serena is now available
    """
    if not enable:
        return {
            "enabled": False,
            "qmd": is_qmd_installed(),
            "serena": is_serena_installed(),
        }

    qmd_ok = is_qmd_installed() or install_qmd()
    serena_ok = is_serena_installed() or install_serena()

    return {
        "enabled": True,
        "qmd": qmd_ok,
        "serena": serena_ok,
    }
