"""Shared utility functions for the installer package."""

from __future__ import annotations

import subprocess


def check_tts_available() -> bool:
    """Check if kokoro TTS is installed in the daemon venv."""
    try:
        from installer.components.mcp import get_daemon_python
        daemon_python = get_daemon_python()
        if not daemon_python.exists():
            return False
        result = subprocess.run(
            [str(daemon_python), "-c", "import kokoro"],
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False
