"""Shared utility functions for the installer package."""

from __future__ import annotations


def check_tts_available() -> bool:
    """Check if Wyoming TTS server is reachable at configured host/port.

    Attempts a TCP connection to the Wyoming server. Returns True if
    the server responds, False otherwise. Used by the installer to
    determine whether TTS can be enabled.
    """
    try:
        import socket
        from spellbook.core.config import config_get, WYOMING_DEFAULT_HOST, WYOMING_DEFAULT_PORT
        host = config_get("tts_wyoming_host") or WYOMING_DEFAULT_HOST
        port = config_get("tts_wyoming_port") or WYOMING_DEFAULT_PORT
        s = socket.create_connection((host, port), timeout=2.0)
        s.close()
        return True
    except Exception:
        return False
