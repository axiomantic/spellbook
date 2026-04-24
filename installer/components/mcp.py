"""
MCP server registration, daemon management, and verification.
"""

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from installer.compat import Platform, get_platform, get_python_executable
from installer.components.source_link import get_source_link_path
from installer.config import get_spellbook_config_dir

# Daemon configuration
# TODO: Consolidate service management with installer.compat.ServiceManager
# to eliminate duplicated launchd/systemd/schtasks logic.
DEFAULT_PORT = 8765
DEFAULT_HOST = "127.0.0.1"
SERVICE_NAME = "spellbook-mcp"
LAUNCHD_LABEL = "com.spellbook.mcp"


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
            ["claude", "mcp", "remove", name, "-s", "user"],
            capture_output=True,
            timeout=10,
        )

        # Add the MCP server with user scope (global, not per-project)
        cmd = ["claude", "mcp", "add", "--scope", "user", name, "--"] + command
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
            ["claude", "mcp", "remove", name, "-s", "user"],
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


def check_daemon_health(timeout: int = 5) -> Tuple[bool, str]:
    """
    Check if the MCP daemon is running and responding to HTTP requests.

    Hits the /health endpoint which returns JSON with status, version,
    and uptime.

    Args:
        timeout: HTTP request timeout in seconds.

    Returns: (healthy, message)
    """
    from urllib.request import Request, urlopen
    from urllib.error import URLError
    import json as _json

    url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/health"

    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = _json.loads(resp.read())
                version = data.get("version", "unknown")
                uptime = data.get("uptime_seconds", 0)
                return (True, f"daemon healthy (v{version}, up {uptime:.0f}s)")
            return (False, f"daemon returned HTTP {resp.status}")
    except URLError as e:
        reason = getattr(e, "reason", str(e))
        return (False, f"daemon not responding: {reason}")
    except TimeoutError:
        return (False, "daemon health check timed out")
    except OSError as e:
        return (False, f"daemon not responding: {e}")


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
        # Look for processes running the spellbook server
        plat = get_platform()
        if plat == Platform.WINDOWS:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process | "
                 "Where-Object {$_.CommandLine -like '*spellbook*server*'} | "
                 "Select-Object -ExpandProperty ProcessId"],
                capture_output=True, text=True, timeout=5,
            )
        else:
            result = subprocess.run(
                ["pgrep", "-f", f"{name}.*server\\.py|spellbook.*server"],
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
                if plat == Platform.WINDOWS:
                    subprocess.run(
                        ["taskkill", "/PID", str(pid)],
                        capture_output=True,
                    )
                    killed += 1
                else:
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


# =============================================================================
# Daemon Venv Isolation
# =============================================================================

def get_daemon_venv_dir() -> Path:
    """Return path to daemon-dedicated venv."""
    return get_spellbook_config_dir() / "daemon-venv"


def get_daemon_python() -> Path:
    """Return path to Python interpreter in daemon venv."""
    venv_dir = get_daemon_venv_dir()
    if platform.system() == "Windows":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _hash_file(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _editable_install_spellbook(daemon_python: Path) -> Tuple[bool, str]:
    """Install spellbook in editable mode pointing at the stable source symlink.

    The symlink (``$SPELLBOOK_CONFIG_DIR/source``) is the indirection point;
    using it here means the editable install survives worktree switches
    without being touched again.
    """
    symlink_path = get_source_link_path()
    try:
        result = subprocess.run(
            [
                "uv", "pip", "install",
                "--python", str(daemon_python),
                "-e", str(symlink_path),
                "--no-deps",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            return (False, f"Failed editable install of spellbook: {error}")
    except FileNotFoundError:
        return (False, "uv not found; cannot install spellbook into daemon venv")
    except subprocess.TimeoutExpired:
        return (False, "Spellbook editable install timed out")
    except OSError as e:
        return (False, f"Spellbook editable install failed: {e}")
    return (True, "")


def _refresh_editable_install(daemon_python: Path) -> Tuple[bool, str]:
    """Force-refresh the editable spellbook install.

    Runs two ``uv pip uninstall`` calls defensively (the second is a
    no-op) to clear any stale ``.dist-info`` left behind by an aborted
    prior install, then re-runs the editable install against the stable
    source symlink.
    """
    for attempt in range(2):
        try:
            result = subprocess.run(
                [
                    "uv", "pip", "uninstall",
                    "--python", str(daemon_python),
                    "spellbook",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError:
            return (False, "uv not found; cannot refresh daemon venv editable install")
        except subprocess.TimeoutExpired:
            return (False, "Spellbook uninstall timed out")
        except OSError as e:
            return (False, f"Spellbook uninstall failed: {e}")

        if result.returncode == 0:
            continue
        # Treat "package not installed" as success: that is the expected
        # state for the second pass, and for first-time installs where
        # the venv has never had spellbook installed. Fail loudly on any
        # other non-zero exit so permission / environment errors are not
        # silently masked.
        stderr_lower = (result.stderr or "").lower()
        not_installed_markers = (
            "is not installed",
            "not installed in environment",
            "no matching distribution",
            "cannot uninstall",
        )
        if any(marker in stderr_lower for marker in not_installed_markers):
            continue
        return (
            False,
            f"Spellbook uninstall failed (pass {attempt + 1}, exit "
            f"{result.returncode}): {result.stderr.strip() or result.stdout.strip()}",
        )

    return _editable_install_spellbook(daemon_python)


def ensure_daemon_venv(
    spellbook_dir: Path,
    force: bool = False,
) -> Tuple[bool, str]:
    """
    Create or update the daemon-dedicated venv from pyproject.toml groups.

    The venv lives at ~/.local/spellbook/daemon-venv/ and is rebuilt
    whenever pyproject.toml changes (detected via SHA256 hash).

    Args:
        spellbook_dir: Path to spellbook installation (contains pyproject.toml).
        force: If True, always rebuild the venv even if hashes match.

    Returns: (success, message)
    """
    pyproject = spellbook_dir / "pyproject.toml"
    if not pyproject.exists():
        return (False, f"pyproject.toml not found: {pyproject}")

    venv_dir = get_daemon_venv_dir()
    daemon_python = get_daemon_python()
    hash_file = venv_dir / ".pyproject-hash"
    source_path_file = venv_dir / ".source-path"

    current_hash = _hash_file(pyproject)
    current_source = str(spellbook_dir.resolve())
    needs_rebuild = force or not daemon_python.exists()

    if not needs_rebuild and hash_file.exists():
        stored_hash = hash_file.read_text().strip()
        if stored_hash != current_hash:
            needs_rebuild = True

    if not needs_rebuild and not hash_file.exists():
        needs_rebuild = True

    # Independent of pyproject hash: if the editable install's source path
    # is unknown or differs from the current source tree, refresh the
    # editable install only (no full venv teardown).
    source_path_changed = False
    if not needs_rebuild:
        if not source_path_file.exists():
            source_path_changed = True
        else:
            stored_source = source_path_file.read_text().strip()
            if stored_source != current_source:
                source_path_changed = True

    if not needs_rebuild and not source_path_changed:
        return (True, "Daemon venv is up to date")

    # Stop any running daemon before rebuilding
    if needs_rebuild:
        stop_daemon(dry_run=False)

        # Remove old venv if it exists
        if venv_dir.exists():
            shutil.rmtree(venv_dir)

        # Create new venv -- prefer uv, fall back to stdlib venv
        venv_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Create venv with --seed to ensure pip is available
            result = subprocess.run(
                ["uv", "venv", str(venv_dir), "--python", "3.12", "--seed"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(f"uv venv failed: {result.stderr.strip()}")
        except (FileNotFoundError, RuntimeError):
            # uv not available or failed; fall back to stdlib venv
            if venv_dir.exists():
                shutil.rmtree(venv_dir)
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "venv", str(venv_dir)],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    error = result.stderr.strip() or result.stdout.strip()
                    return (False, f"Failed to create venv: {error}")
            except subprocess.TimeoutExpired:
                return (False, "Venv creation timed out")
            except OSError as e:
                return (False, f"Venv creation failed: {e}")

        # Install daemon group from pyproject.toml
        try:
            result = subprocess.run(
                [
                    "uv", "pip", "install",
                    "--python", str(daemon_python),
                    "--requirement", str(pyproject),
                    "--group", "daemon",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                error = result.stderr.strip() or result.stdout.strip()
                return (False, f"Failed to install daemon deps: {error}")
        except FileNotFoundError:
            return (False, "uv not found; cannot install deps into daemon venv")
        except subprocess.TimeoutExpired:
            return (False, "Dependency installation timed out")
        except OSError as e:
            return (False, f"Dependency installation failed: {e}")

        # Editable install of spellbook (via the stable source symlink).
        ok, err = _editable_install_spellbook(daemon_python)
        if not ok:
            return (False, err)

        # Store pyproject hash and source-path marker
        hash_file.write_text(current_hash)
        source_path_file.write_text(current_source)

    # Source-path refresh path: venv is otherwise fine but editable install
    # points at a stale worktree (or marker is missing). Force-reinstall
    # the editable install only.
    if not needs_rebuild and source_path_changed:
        ok, err = _refresh_editable_install(daemon_python)
        if not ok:
            return (False, err)
        source_path_file.write_text(current_source)

    return (True, "Daemon venv created and dependencies installed")


# =============================================================================
# Daemon Management
# =============================================================================

def get_spellbook_server_url() -> str:
    """Get the spellbook MCP server URL."""
    return f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/mcp"


TOKEN_PATH = Path.home() / ".local" / "spellbook" / ".mcp-token"


def get_mcp_auth_token() -> Optional[str]:
    """Read the bearer token from ~/.local/spellbook/.mcp-token.

    The token is generated by the MCP server on startup. Returns None
    if the token file doesn't exist or is empty.
    """
    if TOKEN_PATH.exists():
        token = TOKEN_PATH.read_text().strip()
        if token:
            return token
    return None


def get_launchd_plist_path() -> Path:
    """Get path to launchd plist file."""
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"


def get_systemd_service_path() -> Path:
    """Get path to systemd user service file."""
    return Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"


def is_daemon_installed() -> bool:
    """Check if the spellbook daemon is installed as a system service."""
    plat = get_platform()
    if plat == Platform.MACOS:
        return get_launchd_plist_path().exists()
    elif plat == Platform.LINUX:
        return get_systemd_service_path().exists()
    elif plat == Platform.WINDOWS:
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", "SpellbookMCP"],
                capture_output=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    return False


def is_daemon_running() -> bool:
    """Check if the spellbook daemon is running."""
    import socket

    try:
        with socket.create_connection((DEFAULT_HOST, DEFAULT_PORT), timeout=2):
            return True
    except (OSError, TimeoutError):
        return False


def stop_daemon(dry_run: bool = False) -> Tuple[bool, str]:
    """
    Stop the spellbook daemon if running.

    Args:
        dry_run: If True, don't actually stop

    Returns: (success, message)
    """
    if dry_run:
        if is_daemon_running():
            return (True, "Would stop daemon")
        return (True, "Daemon not running")

    plat = get_platform()

    try:
        if plat == Platform.MACOS:
            plist_path = get_launchd_plist_path()
            if plist_path.exists():
                subprocess.run(
                    ["launchctl", "unload", str(plist_path)],
                    capture_output=True
                )
        elif plat == Platform.LINUX:
            subprocess.run(
                ["systemctl", "--user", "stop", SERVICE_NAME],
                capture_output=True
            )
    except FileNotFoundError:
        # systemctl/launchctl not available (e.g., in Docker without systemd)
        pass

    # Give it a moment to stop
    time.sleep(1)

    if is_daemon_running():
        # Graceful stop failed, force kill
        try:
            if plat == Platform.WINDOWS:
                # Find and kill spellbook processes on Windows
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_Process | "
                     "Where-Object {$_.CommandLine -like '*spellbook*server*'} | "
                     "Select-Object -ExpandProperty ProcessId"],
                    capture_output=True, text=True, timeout=10,
                )
                for pid_str in result.stdout.strip().split("\n"):
                    if pid_str.strip():
                        subprocess.run(
                            ["taskkill", "/F", "/PID", pid_str.strip()],
                            capture_output=True,
                        )
            else:
                subprocess.run(
                    ["pkill", "-f", "spellbook/server.py"],
                    capture_output=True
                )
        except FileNotFoundError:
            # pkill/powershell/taskkill not available
            pass
        time.sleep(1)

        if is_daemon_running():
            if plat != Platform.WINDOWS:
                # Last resort: SIGKILL (Unix only)
                try:
                    subprocess.run(
                        ["pkill", "-9", "-f", "spellbook/server.py"],
                        capture_output=True
                    )
                except FileNotFoundError:
                    pass
                time.sleep(1)

            if is_daemon_running():
                return (False, "Daemon still running after force kill attempt")

        return (True, "Daemon stopped (force killed)")

    return (True, "Daemon stopped")


def uninstall_daemon(dry_run: bool = False) -> Tuple[bool, str]:
    """
    Uninstall the spellbook daemon service.

    Args:
        dry_run: If True, don't actually uninstall

    Returns: (success, message)
    """
    if dry_run:
        if is_daemon_installed():
            return (True, "Would uninstall daemon service")
        return (True, "Daemon service not installed")

    plat = get_platform()

    # Stop first
    stop_daemon(dry_run=False)

    if plat == Platform.MACOS:
        plist_path = get_launchd_plist_path()
        if plist_path.exists():
            try:
                subprocess.run(
                    ["launchctl", "unload", str(plist_path)],
                    capture_output=True
                )
            except FileNotFoundError:
                pass
            plist_path.unlink(missing_ok=True)
            return (True, "Daemon service uninstalled")
        return (True, "Daemon service was not installed")

    elif plat == Platform.LINUX:
        service_path = get_systemd_service_path()
        if service_path.exists():
            try:
                subprocess.run(
                    ["systemctl", "--user", "stop", SERVICE_NAME],
                    capture_output=True
                )
                subprocess.run(
                    ["systemctl", "--user", "disable", SERVICE_NAME],
                    capture_output=True
                )
            except FileNotFoundError:
                pass
            service_path.unlink(missing_ok=True)
            try:
                subprocess.run(
                    ["systemctl", "--user", "daemon-reload"],
                    capture_output=True
                )
            except FileNotFoundError:
                pass
            return (True, "Daemon service uninstalled")
        return (True, "Daemon service was not installed")

    elif plat == Platform.WINDOWS:
        try:
            result = subprocess.run(
                ["schtasks", "/Delete", "/TN", "SpellbookMCP", "/F"],
                capture_output=True, text=True,
            )
            if result.returncode == 0 or "does not exist" in result.stderr.lower():
                return (True, "Daemon service uninstalled")
            return (False, f"Failed to uninstall: {result.stderr}")
        except FileNotFoundError:
            return (True, "Daemon service was not installed")

    return (False, f"Unsupported platform: {plat.value}")


def install_daemon(spellbook_dir: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Install and start the spellbook daemon service.

    Creates a dedicated venv for the daemon (if lockfiles exist), then
    delegates to spellbook.daemon.manager.install_service() to generate
    and load the platform service definition.

    Args:
        spellbook_dir: Path to spellbook installation
        dry_run: If True, don't actually install

    Returns: (success, message)
    """
    if dry_run:
        return (True, "Would install daemon service")

    # Ensure daemon venv is set up with pinned deps.
    venv_ok, venv_msg = ensure_daemon_venv(spellbook_dir, force=False)
    if not venv_ok:
        return (False, f"Daemon venv setup failed: {venv_msg}")

    # First, stop and uninstall any existing daemon
    uninstall_daemon(dry_run=False)

    try:
        from spellbook.daemon.manager import install_service

        # Suppress install_service's own print output -- the installer
        # controls formatting via its own print_step/print_success helpers.
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            install_service()

        # Wait for daemon to start and become healthy
        for _ in range(30):
            time.sleep(1)
            healthy, msg = check_daemon_health(timeout=2)
            if healthy:
                return (True, f"Daemon installed and running on {get_spellbook_server_url()}")

        # Final check with longer timeout
        healthy, msg = check_daemon_health(timeout=5)
        if healthy:
            return (True, f"Daemon installed and running on {get_spellbook_server_url()}")
        return (False, f"Daemon installed but not responding ({msg})")

    except SystemExit:
        return (False, "Install failed (service install exited with error)")
    except Exception as e:
        return (False, str(e))


def register_mcp_http_server(
    name: str, url: str, dry_run: bool = False,
    config_dir: Optional[Path] = None,
) -> Tuple[bool, str]:
    """
    Register an MCP server with HTTP transport using claude CLI.

    Reads the bearer token from ~/.local/spellbook/.mcp-token (generated by
    the MCP server on startup) and passes it as an Authorization header.

    Args:
        name: Server name
        url: HTTP URL for the server
        dry_run: If True, don't actually register
        config_dir: If provided, set CLAUDE_CONFIG_DIR so the registration
            targets this specific config directory instead of the default.

    Returns: (success, message)
    """
    if not check_claude_cli_available():
        return (False, "claude CLI not available")

    if dry_run:
        return (True, f"Would register HTTP MCP server: {name} -> {url}")

    # Read bearer token for auth header
    token = get_mcp_auth_token()
    auth_header = f"Authorization: Bearer {token}" if token else None

    # Build environment with optional config dir override
    env = None
    if config_dir is not None:
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(config_dir)}

    try:
        # Always try to remove first (ignore errors)
        subprocess.run(
            ["claude", "mcp", "remove", name, "-s", "user"],
            capture_output=True,
            timeout=10,
            env=env,
        )

        # Add the MCP server with HTTP transport and user scope (global, not per-project)
        # --header is variadic (<header...>) in claude CLI, so it must come AFTER
        # positional args (name, url) to avoid consuming them as header values.
        cmd = ["claude", "mcp", "add", "--transport", "http", "--scope", "user", name, url]
        if auth_header:
            cmd.extend(["--header", auth_header])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)

        if result.returncode == 0:
            return (True, "registered successfully")
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            if "already exists" in error_msg.lower():
                return (True, "already registered")
            return (False, f"registration failed: {error_msg}")

    except subprocess.TimeoutExpired:
        return (False, "command timed out")
    except OSError as e:
        return (False, str(e))
