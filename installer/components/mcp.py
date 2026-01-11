"""
MCP server registration and verification.
"""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class MCPStatus:
    """Status of an MCP server."""

    name: str
    registered: bool
    connected: Optional[bool]  # None if registration check failed
    command: str
    error: Optional[str] = None


def check_claude_cli_available() -> bool:
    """Check if claude CLI is available."""
    try:
        result = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def list_registered_mcp_servers() -> List[MCPStatus]:
    """Get list of registered MCP servers from claude CLI."""
    if not check_claude_cli_available():
        return []

    try:
        result = subprocess.run(
            ["claude", "mcp", "list"], capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            return []

        servers = []
        # Parse the output (format varies, look for server names)
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("-"):
                continue

            # Try to parse "name: command" or just "name"
            if ":" in line:
                parts = line.split(":", 1)
                name = parts[0].strip()
                command = parts[1].strip() if len(parts) > 1 else ""
            else:
                name = line
                command = ""

            if name:
                servers.append(
                    MCPStatus(
                        name=name,
                        registered=True,
                        connected=None,  # We can't easily check this
                        command=command,
                    )
                )

        return servers
    except (subprocess.TimeoutExpired, OSError):
        return []


def is_mcp_registered(name: str) -> bool:
    """Check if an MCP server is registered."""
    servers = list_registered_mcp_servers()
    return any(s.name == name for s in servers)


def register_mcp_server(
    name: str, command: List[str], dry_run: bool = False
) -> Tuple[bool, str]:
    """
    Register an MCP server with claude CLI.

    Args:
        name: Server name
        command: Command to run the server
        dry_run: If True, don't actually register

    Returns: (success, message)
    """
    if not check_claude_cli_available():
        return (False, "claude CLI not available")

    if dry_run:
        return (True, f"Would register MCP server: {name}")

    try:
        # Always try to remove first (ignore errors)
        subprocess.run(
            ["claude", "mcp", "remove", name],
            capture_output=True,
            timeout=10,
        )

        # Add the MCP server
        cmd = ["claude", "mcp", "add", name, "--"] + command
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            return (True, "registered successfully")
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            # Check if it's an "already exists" error - that's actually fine
            if "already exists" in error_msg.lower():
                return (True, "already registered")
            return (False, f"registration failed: {error_msg}")

    except subprocess.TimeoutExpired:
        return (False, "command timed out")
    except OSError as e:
        return (False, str(e))


def unregister_mcp_server(name: str, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Remove an MCP server registration.

    Args:
        name: Server name
        dry_run: If True, don't actually unregister

    Returns: (success, message)
    """
    if not check_claude_cli_available():
        return (False, "claude CLI not available")

    if dry_run:
        if is_mcp_registered(name):
            return (True, f"Would unregister MCP server: {name}")
        return (True, "MCP server not registered")

    try:
        if not is_mcp_registered(name):
            return (True, "was not registered")

        result = subprocess.run(
            ["claude", "mcp", "remove", name],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            return (True, "unregistered successfully")
        elif "not found" in result.stderr.lower():
            return (True, "was not registered")
        else:
            return (False, result.stderr.strip())

    except subprocess.TimeoutExpired:
        return (False, "command timed out")
    except OSError as e:
        return (False, str(e))


def verify_mcp_connectivity(server_path: Path, timeout: int = 10) -> Tuple[bool, str]:
    """
    Verify MCP server can start and respond.

    This does a basic check that the server can be imported/started.

    Args:
        server_path: Path to the server script
        timeout: Timeout in seconds

    Returns: (success, message)
    """
    if not server_path.exists():
        return (False, f"Server not found: {server_path}")

    try:
        # Try to import and check the server can at least be loaded
        result = subprocess.run(
            ["python3", "-c", f"import sys; sys.path.insert(0, '{server_path.parent}'); import server"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=server_path.parent,
        )

        if result.returncode == 0:
            return (True, "server module loads successfully")
        else:
            error = result.stderr.strip() or result.stdout.strip()
            return (False, f"server failed to load: {error}")

    except subprocess.TimeoutExpired:
        return (False, "server load timed out")
    except OSError as e:
        return (False, str(e))


def restart_mcp_server(name: str, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Restart an MCP server by killing its process.

    Claude Code will respawn the MCP server on next use.

    Args:
        name: Server name (used to find the process)
        dry_run: If True, don't actually kill the process

    Returns: (success, message)
    """
    import signal

    if dry_run:
        return (True, f"Would restart MCP server: {name}")

    try:
        # Find processes matching the MCP server
        # Look for processes running the spellbook_mcp server
        result = subprocess.run(
            ["pgrep", "-f", f"{name}.*server\\.py|spellbook_mcp.*server"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0 or not result.stdout.strip():
            return (True, "no running process found (will start on next use)")

        pids = [int(pid) for pid in result.stdout.strip().split("\n") if pid.strip()]

        if not pids:
            return (True, "no running process found (will start on next use)")

        killed = 0
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
                killed += 1
            except (ProcessLookupError, PermissionError):
                # Process already gone or we can't kill it
                pass

        if killed > 0:
            return (True, f"terminated {killed} process(es), will respawn on next use")
        else:
            return (True, "processes already stopped")

    except subprocess.TimeoutExpired:
        return (False, "process search timed out")
    except (OSError, ValueError) as e:
        return (False, str(e))


def check_gemini_cli_available() -> bool:
    """Check if gemini CLI is available."""
    try:
        result = subprocess.run(
            ["gemini", "--version"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
