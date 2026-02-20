#!/usr/bin/env python3
"""Watchdog for spellbook MCP server on Windows.

Restarts the server process if it crashes, with exponential backoff.
Used by Task Scheduler as the primary entry point.

Usage:
    python scripts/spellbook-watchdog.py
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def get_server_cmd() -> list[str]:
    """Build the command to start the MCP server."""
    spellbook_dir = os.environ.get(
        "SPELLBOOK_DIR", str(Path(__file__).parent.parent)
    )
    uv = shutil.which("uv")
    if uv:
        return [uv, "run", "python", "-m", "spellbook_mcp.server"]
    return [sys.executable, "-m", "spellbook_mcp.server"]


def main() -> None:
    """Run the watchdog loop with exponential backoff."""
    cmd = get_server_cmd()
    max_failures = 10
    failures = 0
    backoff = 1

    spellbook_dir = os.environ.get(
        "SPELLBOOK_DIR", str(Path(__file__).parent.parent)
    )

    while failures < max_failures:
        print(f"[watchdog] Starting server (attempt {failures + 1})")
        proc = subprocess.Popen(cmd, cwd=spellbook_dir)
        proc.wait()

        if proc.returncode == 0:
            print("[watchdog] Server exited cleanly")
            break

        failures += 1
        wait = min(backoff, 300)  # Cap at 5 minutes
        print(
            f"[watchdog] Server crashed (exit {proc.returncode}). "
            f"Restarting in {wait}s..."
        )
        time.sleep(wait)
        backoff *= 2

    if failures >= max_failures:
        print(f"[watchdog] Max failures ({max_failures}) reached. Giving up.")
        sys.exit(1)


if __name__ == "__main__":
    main()
