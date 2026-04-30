"""Platform service file generation and installation (launchd/systemd/schtasks).

Provides functions to generate, install, and uninstall the spellbook MCP
server as a system service on macOS (launchd), Linux (systemd), and
Windows (Task Scheduler).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path

logger = logging.getLogger(__name__)

from spellbook.daemon._paths import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    LAUNCHD_LABEL,
    SERVICE_NAME,
    get_config_dir,
    get_daemon_python,
    get_err_log_file,
    get_host,
    get_log_file,
    get_platform,
    get_port,
    get_server_script,
    get_server_url,
    get_spellbook_dir,
    get_uv_path,
)


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------


def check_dependencies() -> bool:
    """Check all required dependencies and prompt to install if missing.

    Returns True if all dependencies are present.
    """
    missing: list[dict] = []

    if not shutil.which("uv"):
        missing.append(
            {
                "name": "uv",
                "description": "Fast Python package manager (required)",
                "install": [
                    "curl -LsSf https://astral.sh/uv/install.sh | sh",
                    "brew install uv",
                    "pipx install uv",
                ],
                "docs": "https://docs.astral.sh/uv/getting-started/installation/",
            }
        )

    if not shutil.which("git"):
        missing.append(
            {
                "name": "git",
                "description": "Version control (recommended for full functionality)",
                "install": [
                    "brew install git",
                    "apt install git",
                    "xcode-select --install  # macOS",
                ],
                "docs": "https://git-scm.com/downloads",
                "optional": True,
            }
        )

    if not missing:
        return True

    required_missing = [d for d in missing if not d.get("optional")]
    optional_missing = [d for d in missing if d.get("optional")]

    if required_missing:
        print("Error: Missing required dependencies:", file=sys.stderr)
        print("", file=sys.stderr)
        for dep in required_missing:
            print(f"  {dep['name']}: {dep['description']}", file=sys.stderr)
            print("  Install with one of:", file=sys.stderr)
            for cmd in dep["install"]:
                print(f"    {cmd}", file=sys.stderr)
            print(f"  More info: {dep['docs']}", file=sys.stderr)
            print("", file=sys.stderr)

    if optional_missing:
        print("Warning: Missing optional dependencies:", file=sys.stderr)
        for dep in optional_missing:
            print(f"  {dep['name']}: {dep['description']}", file=sys.stderr)
        print("", file=sys.stderr)

    return len(required_missing) == 0


def check_uv_installed() -> bool:
    """Check if uv is installed and prompt to install if not."""
    return check_dependencies()


# ---------------------------------------------------------------------------
# PATH helpers for daemon environments
# ---------------------------------------------------------------------------


def _resolve_cli_tool_dirs(paths: list[str]) -> list[str]:
    """Resolve paths of supported CLI tools and add their directories.

    Uses shutil.which() to find the actual location of each supported CLI
    tool.  This captures tools installed via mise, asdf, or other version
    managers whose shim directories are not in the hardcoded PATH list.
    """
    cli_tools = ["gemini", "claude", "codex", "opencode", "forge"]
    resolved = list(paths)
    seen = set(resolved)
    for tool in cli_tools:
        tool_path = shutil.which(tool)
        if tool_path:
            tool_dir = str(Path(tool_path).resolve().parent)
            if tool_dir not in seen:
                resolved.append(tool_dir)
                seen.add(tool_dir)
    return resolved


def _get_darwin_daemon_path() -> str:
    """Get PATH for daemon environment on macOS.

    launchd doesn't inherit shell PATH, so we need to explicitly set it.
    Includes Homebrew paths for both Apple Silicon and Intel Macs, plus
    directories of any supported CLI tools found via shutil.which().
    """
    import platform as _platform

    paths: list[str] = []

    if _platform.machine() == "arm64":
        paths.append("/opt/homebrew/bin")
        paths.append("/opt/homebrew/sbin")
    else:
        paths.append("/usr/local/bin")
        paths.append("/usr/local/sbin")

    home = Path.home()
    if (home / ".local" / "bin").exists():
        paths.append(str(home / ".local" / "bin"))
    if (home / ".cargo" / "bin").exists():
        paths.append(str(home / ".cargo" / "bin"))

    paths.extend(["/usr/bin", "/bin", "/usr/sbin", "/sbin"])
    paths = _resolve_cli_tool_dirs(paths)
    return os.pathsep.join(paths)


def _get_linux_daemon_path() -> str:
    """Get PATH for Linux daemon environment."""
    paths: list[str] = []
    home = Path.home()

    if (home / ".local" / "bin").exists():
        paths.append(str(home / ".local" / "bin"))
    if (home / ".cargo" / "bin").exists():
        paths.append(str(home / ".cargo" / "bin"))
    if Path("/home/linuxbrew/.linuxbrew/bin").exists():
        paths.append("/home/linuxbrew/.linuxbrew/bin")

    paths.extend(
        ["/usr/local/bin", "/usr/bin", "/bin", "/usr/local/sbin", "/usr/sbin", "/sbin"]
    )
    paths = _resolve_cli_tool_dirs(paths)
    return os.pathsep.join(paths)


# ---------------------------------------------------------------------------
# macOS launchd
# ---------------------------------------------------------------------------


def get_launchd_plist_path() -> Path:
    """Get path to launchd plist file."""
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"


def _get_service_source_dir() -> Path:
    """Return the path that launchd/systemd service definitions should bake in.

    Prefers the stable source symlink (``$SPELLBOOK_CONFIG_DIR/source``) so
    the service file survives worktree switches. Falls back to the
    resolved source directory if the symlink is not yet present (e.g.
    very first install before the symlink is created).
    """
    try:
        from installer.components.source_link import get_source_link_path
        link = get_source_link_path()
        if link.exists() or link.is_symlink():
            return link
    except Exception as exc:
        logger.debug(
            "source symlink lookup failed; falling back to resolved spellbook dir: %s",
            exc,
            exc_info=True,
        )
    return get_spellbook_dir()


def _generate_launchd_plist() -> str:
    """Generate launchd plist content."""
    spellbook_dir = _get_service_source_dir()
    log_file = get_log_file()
    err_log_file = get_err_log_file()
    port = get_port()
    host = get_host()
    daemon_path = _get_darwin_daemon_path()

    daemon_python = get_daemon_python()
    if daemon_python:
        program_args = (
            f"                <string>{daemon_python}</string>\n"
            f"                <string>-m</string>\n"
            f"                <string>spellbook.mcp</string>"
        )
    else:
        uv_path = get_uv_path()
        program_args = (
            f"                <string>{uv_path}</string>\n"
            f"                <string>run</string>\n"
            f"                <string>python</string>\n"
            f"                <string>-m</string>\n"
            f"                <string>spellbook.mcp</string>"
        )

    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{LAUNCHD_LABEL}</string>

            <key>ProgramArguments</key>
            <array>
{program_args}
            </array>

            <key>EnvironmentVariables</key>
            <dict>
                <key>PATH</key>
                <string>{daemon_path}</string>
                <key>SPELLBOOK_MCP_TRANSPORT</key>
                <string>streamable-http</string>
                <key>SPELLBOOK_MCP_HOST</key>
                <string>{host}</string>
                <key>SPELLBOOK_MCP_PORT</key>
                <string>{port}</string>
                <key>SPELLBOOK_DIR</key>
                <string>{spellbook_dir}</string>
            </dict>

            <key>RunAtLoad</key>
            <true/>

            <key>KeepAlive</key>
            <true/>

            <key>StandardOutPath</key>
            <string>{log_file}</string>

            <key>StandardErrorPath</key>
            <string>{err_log_file}</string>

            <key>WorkingDirectory</key>
            <string>{spellbook_dir}</string>
        </dict>
        </plist>
    """)


def _install_launchd() -> tuple[bool, str]:
    """Install launchd service on macOS."""
    plist_path = get_launchd_plist_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    if plist_path.exists():
        subprocess.run(
            ["launchctl", "unload", str(plist_path)], capture_output=True
        )

    plist_content = _generate_launchd_plist()
    plist_path.write_text(plist_content, encoding="utf-8")

    result = subprocess.run(
        ["launchctl", "load", str(plist_path)], capture_output=True, text=True
    )
    if result.returncode != 0:
        return False, f"Failed to load service: {result.stderr}"
    return True, f"Installed launchd service: {plist_path}"


def _uninstall_launchd() -> tuple[bool, str]:
    """Uninstall launchd service on macOS."""
    plist_path = get_launchd_plist_path()
    if not plist_path.exists():
        return True, "Service not installed"

    subprocess.run(
        ["launchctl", "unload", str(plist_path)], capture_output=True, text=True
    )
    plist_path.unlink(missing_ok=True)
    return True, "Uninstalled launchd service"


def is_launchd_running() -> bool:
    """Check if launchd service is running."""
    result = subprocess.run(
        ["launchctl", "list", LAUNCHD_LABEL], capture_output=True
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Linux systemd
# ---------------------------------------------------------------------------


def get_systemd_service_path() -> Path:
    """Get path to systemd user service file."""
    return (
        Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"
    )


def _generate_systemd_service() -> str:
    """Generate systemd user service content."""
    spellbook_dir = _get_service_source_dir()
    port = get_port()
    host = get_host()
    daemon_path = _get_linux_daemon_path()

    daemon_python = get_daemon_python()
    if daemon_python:
        exec_start = f"{daemon_python} -m spellbook.mcp"
    else:
        uv_path = get_uv_path()
        exec_start = f"{uv_path} run python -m spellbook.mcp"

    return textwrap.dedent(f"""\
        [Unit]
        Description=Spellbook MCP Server
        After=network.target

        [Service]
        Type=simple
        ExecStart={exec_start}
        WorkingDirectory={spellbook_dir}
        Restart=always
        RestartSec=5

        Environment=PATH={daemon_path}
        Environment=SPELLBOOK_MCP_TRANSPORT=streamable-http
        Environment=SPELLBOOK_MCP_HOST={host}
        Environment=SPELLBOOK_MCP_PORT={port}
        Environment=SPELLBOOK_DIR={spellbook_dir}

        [Install]
        WantedBy=default.target
    """)


def _install_systemd() -> tuple[bool, str]:
    """Install systemd user service on Linux."""
    if not shutil.which("systemctl"):
        return False, "systemctl not found (systemd not available in this environment)"

    service_path = get_systemd_service_path()
    service_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            ["systemctl", "--user", "stop", SERVICE_NAME], capture_output=True
        )
    except FileNotFoundError:
        return False, "systemctl not found"

    service_content = _generate_systemd_service()
    service_path.write_text(service_content, encoding="utf-8")

    result = subprocess.run(
        ["systemctl", "--user", "daemon-reload"], capture_output=True, text=True
    )
    if result.returncode != 0:
        return False, f"Failed to reload systemd: {result.stderr}"

    result = subprocess.run(
        ["systemctl", "--user", "enable", SERVICE_NAME],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, f"Failed to enable service: {result.stderr}"

    result = subprocess.run(
        ["systemctl", "--user", "start", SERVICE_NAME],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, f"Failed to start service: {result.stderr}"

    try:
        subprocess.run(
            ["loginctl", "enable-linger", os.environ.get("USER", "")],
            capture_output=True,
        )
    except FileNotFoundError:
        pass

    return True, f"Installed systemd service: {service_path}"


def _uninstall_systemd() -> tuple[bool, str]:
    """Uninstall systemd user service on Linux."""
    service_path = get_systemd_service_path()
    if not service_path.exists():
        return True, "Service not installed"

    try:
        subprocess.run(
            ["systemctl", "--user", "stop", SERVICE_NAME], capture_output=True
        )
        subprocess.run(
            ["systemctl", "--user", "disable", SERVICE_NAME], capture_output=True
        )
    except FileNotFoundError:
        pass

    service_path.unlink(missing_ok=True)

    try:
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"], capture_output=True
        )
    except FileNotFoundError:
        pass

    return True, "Uninstalled systemd service"


def is_systemd_running() -> bool:
    """Check if systemd service is running."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", SERVICE_NAME],
            capture_output=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


# ---------------------------------------------------------------------------
# Platform-agnostic public API
# ---------------------------------------------------------------------------


def is_service_installed() -> bool:
    """Check if the system service is installed."""
    plat = get_platform()
    if plat == "darwin":
        return get_launchd_plist_path().exists()
    elif plat == "linux":
        return get_systemd_service_path().exists()
    elif plat == "windows":
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", "SpellbookMCP"],
                capture_output=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    return False


def is_service_running() -> bool:
    """Check if the system service is running."""
    plat = get_platform()
    if plat == "darwin":
        return is_launchd_running()
    elif plat == "linux":
        return is_systemd_running()
    elif plat == "windows":
        return check_server_health(timeout=2.0)
    return False


def check_server_health(timeout: float = 5.0) -> bool:
    """Check if server is responding by testing if the port is open."""
    import socket

    host = get_host()
    port = get_port()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def generate_service_file(platform: str) -> str:
    """Generate a service file for the given platform.

    Args:
        platform: One of 'darwin', 'linux'.

    Returns:
        The service file content as a string.

    Raises:
        ValueError: If the platform is not supported.
    """
    if platform == "darwin":
        return _generate_launchd_plist()
    elif platform == "linux":
        return _generate_systemd_service()
    else:
        raise ValueError(
            f"Unsupported platform for service file generation: {platform!r}. "
            f"Supported platforms: 'darwin', 'linux'."
        )


def install_service() -> None:
    """Install the system service for the current platform.

    Prints progress and results to stdout/stderr.
    """
    plat = get_platform()

    if not get_daemon_python() and not check_uv_installed():
        sys.exit(1)

    server_script = get_server_script()
    if not server_script.exists():
        print(f"Error: Server script not found: {server_script}", file=sys.stderr)
        sys.exit(1)

    print("Installing spellbook MCP server as system service...")
    print(f"  Platform: {plat}")
    print(f"  Server: {server_script}")
    print(f"  URL: {get_server_url()}")

    if plat == "darwin":
        success, msg = _install_launchd()
    elif plat == "linux":
        success, msg = _install_systemd()
    elif plat == "windows":
        from installer.compat import ServiceManager, mcp_service_config

        mgr = ServiceManager(mcp_service_config(get_spellbook_dir(), get_port(), get_host()))
        success, msg = mgr.install()
    else:
        print(f"Error: Unsupported platform: {plat}", file=sys.stderr)
        sys.exit(1)

    if success:
        print(f"\n{msg}")
        print("\nServer will start automatically on boot.")
        print(f"Log file: {get_log_file()}")

        print("\nWaiting for server to start...", end=" ", flush=True)
        for _ in range(10):
            time.sleep(1)
            if check_server_health():
                print("OK")
                break
        else:
            print("(may still be starting)")

        print(f"\nTo configure Claude Code to use the HTTP server:")
        print(f"  claude mcp add --transport http spellbook {get_server_url()}")
    else:
        print(f"\nError: {msg}", file=sys.stderr)
        sys.exit(1)


def uninstall_service() -> None:
    """Uninstall the system service for the current platform.

    Prints progress and results to stdout/stderr.
    """
    plat = get_platform()
    print("Uninstalling spellbook MCP server system service...")

    if plat == "darwin":
        success, msg = _uninstall_launchd()
    elif plat == "linux":
        success, msg = _uninstall_systemd()
    elif plat == "windows":
        from installer.compat import ServiceManager, mcp_service_config

        mgr = ServiceManager(mcp_service_config(get_spellbook_dir(), get_port(), get_host()))
        success, msg = mgr.uninstall()
    else:
        print(f"Error: Unsupported platform: {plat}", file=sys.stderr)
        sys.exit(1)

    print(msg)
    if not success:
        sys.exit(1)
