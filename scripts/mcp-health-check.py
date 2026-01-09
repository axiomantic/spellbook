#!/usr/bin/env python3
"""MCP health check script for verifying spellbook MCP is running inside coding assistants.

Supports: Claude Code, Gemini CLI, Codex, OpenCode

Verifies that the spellbook MCP server is:
1. Configured in the coding assistant
2. Server script exists and Python is available
3. For Claude: actually connected (via `claude mcp get`)

Usage:
    # Fast config check (recommended)
    python3 scripts/mcp-health-check.py --config-only

    # Check specific platform
    python3 scripts/mcp-health-check.py --platform claude --config-only
    python3 scripts/mcp-health-check.py --platform gemini
    python3 scripts/mcp-health-check.py --platform codex
    python3 scripts/mcp-health-check.py --platform opencode

    # Check ALL installed platforms
    python3 scripts/mcp-health-check.py --platform all --config-only

    # Full Claude connection check (slow - connects to all MCP servers)
    python3 scripts/mcp-health-check.py --platform claude

    # Wait for MCP to become healthy with retries
    python3 scripts/mcp-health-check.py --wait --timeout 60

    # JSON output for scripting
    python3 scripts/mcp-health-check.py --platform all --config-only --json

    # Verbose output with full diagnostics
    python3 scripts/mcp-health-check.py --config-only --verbose

Exit codes:
    0: Healthy (all platforms if --platform all)
    1: Not healthy or error
    130: Interrupted (Ctrl+C)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DiagnosticResult:
    """Result of a diagnostic check."""
    check: str
    passed: bool
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    """Overall health check result."""
    healthy: bool
    platform: str
    server_name: str = "spellbook"
    connected: bool = False
    configured: bool = False
    process_running: bool = False
    diagnostics: list[DiagnosticResult] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "platform": self.platform,
            "server_name": self.server_name,
            "connected": self.connected,
            "configured": self.configured,
            "process_running": self.process_running,
            "diagnostics": [
                {
                    "check": d.check,
                    "passed": d.passed,
                    "message": d.message,
                    "details": d.details,
                }
                for d in self.diagnostics
            ],
            "error": self.error,
        }


def run_command(cmd: list[str], timeout: float = 10.0) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return -1, "", str(e)


def check_claude_config_only(verbose: bool = False) -> HealthCheckResult:
    """Check MCP configuration without connecting to all servers (fast mode).

    Uses `claude mcp get spellbook` which is much faster than `claude mcp list`
    because it doesn't connect to all MCP servers.
    """
    result = HealthCheckResult(healthy=False, platform="claude")

    # Check if claude CLI is available
    if not shutil.which("claude"):
        result.error = "Claude CLI not found in PATH"
        result.diagnostics.append(DiagnosticResult(
            check="cli_available",
            passed=False,
            message="Claude CLI not found",
            details={"suggestion": "Install Claude Code or add it to PATH"},
        ))
        return result

    result.diagnostics.append(DiagnosticResult(
        check="cli_available",
        passed=True,
        message="Claude CLI found",
    ))

    # Use `claude mcp get spellbook` which is faster than `mcp list` but still
    # connects to the server to check status, so it can take 20-30s
    returncode, stdout, stderr = run_command(
        ["claude", "mcp", "get", "spellbook"],
        timeout=45.0,
    )

    if returncode != 0:
        # Server not configured
        result.configured = False
        if "not found" in stderr.lower() or "not found" in stdout.lower():
            result.error = "Spellbook MCP not configured in Claude Code"
            result.diagnostics.append(DiagnosticResult(
                check="mcp_configured",
                passed=False,
                message="Spellbook MCP not found in Claude Code",
                details={"suggestion": "Run the spellbook installer: uv run install.py"},
            ))
        else:
            result.error = f"Failed to get MCP config: {stderr or stdout}"
            result.diagnostics.append(DiagnosticResult(
                check="mcp_configured",
                passed=False,
                message="Failed to query MCP configuration",
                details={"stderr": stderr, "stdout": stdout},
            ))
        return result

    # Parse the output to extract configuration
    # Format:
    # spellbook:
    #   Scope: Local config (private to you in this project)
    #   Status: ✓ Connected
    #   Type: stdio
    #   Command: python3
    #   Args: /path/to/server.py
    result.configured = True

    # Check connection status from output
    # Note: `claude mcp get` spawns a new process to test connection, which may
    # fail even if the MCP works fine in actual Claude sessions. We primarily
    # care about whether the MCP is CONFIGURED correctly for installation verification.
    if "✓ Connected" in stdout:
        result.connected = True
        result.diagnostics.append(DiagnosticResult(
            check="mcp_connected",
            passed=True,
            message="Spellbook MCP is connected",
        ))
    elif "✗" in stdout:
        result.connected = False
        result.diagnostics.append(DiagnosticResult(
            check="mcp_connected",
            passed=False,
            message="Spellbook MCP is configured but not connected (may work in actual sessions)",
            details={"output": stdout.strip()},
        ))

    # Extract scope
    scope_match = re.search(r"Scope:\s*(.+)", stdout)
    if scope_match:
        scope = scope_match.group(1).strip()
        result.diagnostics.append(DiagnosticResult(
            check="mcp_scope",
            passed=True,
            message=f"Configuration scope: {scope}",
        ))

    # Extract and verify command
    command_match = re.search(r"Command:\s*(.+)", stdout)
    if command_match:
        command = command_match.group(1).strip()
        if shutil.which(command):
            result.diagnostics.append(DiagnosticResult(
                check="command_available",
                passed=True,
                message=f"Command found: {command}",
            ))
        else:
            result.healthy = False
            result.diagnostics.append(DiagnosticResult(
                check="command_available",
                passed=False,
                message=f"Command not found: {command}",
            ))

    # Extract and verify args (server script path)
    args_match = re.search(r"Args:\s*(.+)", stdout)
    if args_match:
        args = args_match.group(1).strip()
        server_path = args.split()[0] if args else None
        if server_path:
            if Path(server_path).exists():
                result.diagnostics.append(DiagnosticResult(
                    check="server_script_exists",
                    passed=True,
                    message=f"Server script exists: {server_path}",
                ))
            else:
                result.healthy = False
                result.diagnostics.append(DiagnosticResult(
                    check="server_script_exists",
                    passed=False,
                    message=f"Server script not found: {server_path}",
                    details={"suggestion": "Re-run the spellbook installer"},
                ))

    # Check for running processes
    _check_running_processes(result)

    # Store full config output for verbose mode
    result.diagnostics.append(DiagnosticResult(
        check="mcp_config_details",
        passed=True,
        message="Full MCP configuration",
        details={"config": stdout.strip()},
    ))

    # For config-only check, mark as healthy if:
    # 1. MCP is configured
    # 2. Server script exists
    # 3. Python command is available
    # Connection status is informational but not required
    script_exists = any(
        d.check == "server_script_exists" and d.passed
        for d in result.diagnostics
    )
    command_available = any(
        d.check == "command_available" and d.passed
        for d in result.diagnostics
    )

    if result.configured and script_exists and command_available:
        result.healthy = True

    return result


def check_claude_mcp(verbose: bool = False) -> HealthCheckResult:
    """Check MCP status in Claude Code using the `claude mcp` CLI."""
    result = HealthCheckResult(healthy=False, platform="claude")

    # Check if claude CLI is available
    if not shutil.which("claude"):
        result.error = "Claude CLI not found in PATH"
        result.diagnostics.append(DiagnosticResult(
            check="cli_available",
            passed=False,
            message="Claude CLI not found",
            details={"suggestion": "Install Claude Code or add it to PATH"},
        ))
        return result

    result.diagnostics.append(DiagnosticResult(
        check="cli_available",
        passed=True,
        message="Claude CLI found",
    ))

    # Run `claude mcp list` to see all configured MCPs
    # This command can be slow (60s+) because it connects to each server
    returncode, stdout, stderr = run_command(["claude", "mcp", "list"], timeout=120.0)

    if returncode != 0:
        result.error = f"Failed to run 'claude mcp list': {stderr}"
        result.diagnostics.append(DiagnosticResult(
            check="mcp_list",
            passed=False,
            message="Failed to list MCP servers",
            details={"stderr": stderr, "returncode": returncode},
        ))
        return result

    # Parse the output to find spellbook status
    # Format: "spellbook: python3 ... - ✓ Connected" or "- ✗ Failed to connect"
    lines = stdout.strip().split("\n")

    spellbook_line = None
    for line in lines:
        if line.startswith("spellbook:"):
            spellbook_line = line
            break

    if not spellbook_line:
        result.configured = False
        result.error = "Spellbook MCP not configured in Claude Code"
        result.diagnostics.append(DiagnosticResult(
            check="mcp_configured",
            passed=False,
            message="Spellbook MCP not found in Claude Code configuration",
            details={
                "suggestion": "Run the spellbook installer or manually add the MCP server",
                "mcp_servers_found": [l.split(":")[0] for l in lines if ":" in l],
            },
        ))
        return result

    result.configured = True
    result.diagnostics.append(DiagnosticResult(
        check="mcp_configured",
        passed=True,
        message="Spellbook MCP is configured",
        details={"config_line": spellbook_line},
    ))

    # Check if connected
    if "✓ Connected" in spellbook_line:
        result.connected = True
        result.healthy = True
        result.diagnostics.append(DiagnosticResult(
            check="mcp_connected",
            passed=True,
            message="Spellbook MCP is connected and healthy",
        ))
    elif "✗ Failed to connect" in spellbook_line:
        result.connected = False
        result.error = "Spellbook MCP failed to connect"
        result.diagnostics.append(DiagnosticResult(
            check="mcp_connected",
            passed=False,
            message="Spellbook MCP failed to connect",
            details={"status_line": spellbook_line},
        ))
        # Get more details
        _add_connection_diagnostics(result, verbose)
    else:
        result.connected = False
        result.error = f"Unknown MCP status: {spellbook_line}"
        result.diagnostics.append(DiagnosticResult(
            check="mcp_connected",
            passed=False,
            message=f"Unknown status: {spellbook_line}",
        ))

    return result


def _add_connection_diagnostics(result: HealthCheckResult, verbose: bool) -> None:
    """Add detailed diagnostics when connection fails."""
    # Get detailed config with `claude mcp get spellbook`
    returncode, stdout, stderr = run_command(["claude", "mcp", "get", "spellbook"])

    if returncode == 0:
        result.diagnostics.append(DiagnosticResult(
            check="mcp_config_details",
            passed=True,
            message="Retrieved MCP configuration",
            details={"config": stdout.strip()},
        ))

        # Parse out the command and args
        command_match = re.search(r"Command:\s*(.+)", stdout)
        args_match = re.search(r"Args:\s*(.+)", stdout)

        if command_match:
            command = command_match.group(1).strip()
            args = args_match.group(1).strip() if args_match else ""

            # Check if the server script exists
            server_path = args.split()[0] if args else None
            if server_path:
                if Path(server_path).exists():
                    result.diagnostics.append(DiagnosticResult(
                        check="server_script_exists",
                        passed=True,
                        message=f"Server script exists: {server_path}",
                    ))
                else:
                    result.diagnostics.append(DiagnosticResult(
                        check="server_script_exists",
                        passed=False,
                        message=f"Server script not found: {server_path}",
                        details={"suggestion": "Re-run the spellbook installer"},
                    ))

            # Check if the command (python3) is available
            if shutil.which(command):
                result.diagnostics.append(DiagnosticResult(
                    check="python_available",
                    passed=True,
                    message=f"Python interpreter found: {command}",
                ))
            else:
                result.diagnostics.append(DiagnosticResult(
                    check="python_available",
                    passed=False,
                    message=f"Python interpreter not found: {command}",
                ))

    # Check for running processes
    _check_running_processes(result)

    # Try to run the server directly and capture any startup errors
    if verbose:
        _check_server_startup(result)


def _check_running_processes(result: HealthCheckResult) -> None:
    """Check if there are any spellbook MCP server processes running."""
    returncode, stdout, stderr = run_command(
        ["pgrep", "-f", "spellbook_mcp/server.py"]
    )

    if returncode == 0 and stdout.strip():
        pids = stdout.strip().split("\n")
        result.process_running = True
        result.diagnostics.append(DiagnosticResult(
            check="process_running",
            passed=True,
            message=f"Found {len(pids)} running spellbook MCP process(es)",
            details={"pids": pids},
        ))
    else:
        result.process_running = False
        result.diagnostics.append(DiagnosticResult(
            check="process_running",
            passed=False,
            message="No spellbook MCP processes found",
            details={"suggestion": "The server starts when Claude Code connects to it"},
        ))


def _check_server_startup(result: HealthCheckResult) -> None:
    """Try to start the server and capture any import/startup errors."""
    spellbook_dir = os.environ.get(
        "SPELLBOOK_DIR",
        str(Path(__file__).parent.parent)
    )
    server_path = Path(spellbook_dir) / "spellbook_mcp" / "server.py"

    if not server_path.exists():
        result.diagnostics.append(DiagnosticResult(
            check="server_import",
            passed=False,
            message=f"Server script not found: {server_path}",
        ))
        return

    # Try to import the server module and check for errors
    returncode, stdout, stderr = run_command(
        ["python3", "-c", f"import sys; sys.path.insert(0, '{spellbook_dir}'); from spellbook_mcp import server; print('Import OK')"],
        timeout=10.0,
    )

    if returncode == 0:
        result.diagnostics.append(DiagnosticResult(
            check="server_import",
            passed=True,
            message="Server module imports successfully",
        ))
    else:
        result.diagnostics.append(DiagnosticResult(
            check="server_import",
            passed=False,
            message="Server module failed to import",
            details={
                "stderr": stderr,
                "suggestion": "Check for missing dependencies: uv pip install -e .",
            },
        ))


def check_gemini_mcp(verbose: bool = False) -> HealthCheckResult:
    """Check MCP status in Gemini CLI.

    Gemini uses native extensions linked via `gemini extensions link`.
    The spellbook extension provides MCP tools via the extension's MCP server.
    """
    result = HealthCheckResult(healthy=False, platform="gemini")

    # Get spellbook directory from env or script location
    spellbook_dir = Path(os.environ.get(
        "SPELLBOOK_DIR",
        str(Path(__file__).parent.parent)
    ))

    # Check if gemini CLI is available
    gemini_available = shutil.which("gemini") is not None
    gemini_config_dir = Path.home() / ".gemini"

    if not gemini_available and not gemini_config_dir.exists():
        result.error = "Gemini CLI not found and ~/.gemini does not exist"
        result.diagnostics.append(DiagnosticResult(
            check="platform_available",
            passed=False,
            message="Gemini CLI not installed",
            details={"suggestion": "Install Gemini CLI: npm install -g @anthropic/gemini-cli"},
        ))
        return result

    result.diagnostics.append(DiagnosticResult(
        check="platform_available",
        passed=True,
        message=f"Gemini CLI: {'found' if gemini_available else 'not in PATH'}, config dir: {'exists' if gemini_config_dir.exists() else 'missing'}",
    ))

    # Check for extension symlink at ~/.gemini/extensions/spellbook
    extension_link = gemini_config_dir / "extensions" / "spellbook"
    extension_source = spellbook_dir / "extensions" / "gemini"

    if extension_link.is_symlink():
        result.configured = True
        result.diagnostics.append(DiagnosticResult(
            check="extension_linked",
            passed=True,
            message=f"Extension symlink exists: {extension_link}",
            details={"target": str(extension_link.resolve())},
        ))

        # Verify it points to the right place
        try:
            target = extension_link.resolve()
            if extension_source.resolve() == target or "spellbook" in str(target):
                result.diagnostics.append(DiagnosticResult(
                    check="extension_target",
                    passed=True,
                    message="Extension points to spellbook",
                ))
            else:
                result.diagnostics.append(DiagnosticResult(
                    check="extension_target",
                    passed=False,
                    message=f"Extension points to unexpected location: {target}",
                ))
        except OSError as e:
            result.diagnostics.append(DiagnosticResult(
                check="extension_target",
                passed=False,
                message=f"Cannot resolve symlink: {e}",
            ))
    elif extension_link.exists():
        result.configured = True
        result.diagnostics.append(DiagnosticResult(
            check="extension_linked",
            passed=True,
            message="Extension directory exists (not a symlink)",
        ))
    else:
        result.configured = False
        result.error = "Spellbook extension not linked in Gemini"
        result.diagnostics.append(DiagnosticResult(
            check="extension_linked",
            passed=False,
            message="Extension not found at ~/.gemini/extensions/spellbook",
            details={
                "suggestion": f"Run: gemini extensions link {extension_source}",
                "expected_path": str(extension_link),
            },
        ))
        return result

    # Check that extension source directory exists
    if extension_source.exists():
        result.diagnostics.append(DiagnosticResult(
            check="extension_source",
            passed=True,
            message=f"Extension source exists: {extension_source}",
        ))
    else:
        result.diagnostics.append(DiagnosticResult(
            check="extension_source",
            passed=False,
            message=f"Extension source not found: {extension_source}",
        ))

    # Check server script exists
    server_path = spellbook_dir / "spellbook_mcp" / "server.py"
    if server_path.exists():
        result.diagnostics.append(DiagnosticResult(
            check="server_script_exists",
            passed=True,
            message=f"Server script exists: {server_path}",
        ))
    else:
        result.healthy = False
        result.diagnostics.append(DiagnosticResult(
            check="server_script_exists",
            passed=False,
            message=f"Server script not found: {server_path}",
        ))
        return result

    # If CLI is available, also run `gemini extensions list` to verify
    if gemini_available:
        returncode, stdout, stderr = run_command(["gemini", "extensions", "list"], timeout=15.0)
        if returncode == 0:
            if "spellbook" in stdout.lower():
                result.diagnostics.append(DiagnosticResult(
                    check="cli_extensions_list",
                    passed=True,
                    message="Extension appears in 'gemini extensions list'",
                ))
            else:
                result.diagnostics.append(DiagnosticResult(
                    check="cli_extensions_list",
                    passed=False,
                    message="Extension NOT in 'gemini extensions list' output",
                    details={"output": stdout.strip()},
                ))
        else:
            result.diagnostics.append(DiagnosticResult(
                check="cli_extensions_list",
                passed=False,
                message=f"Failed to run 'gemini extensions list': {stderr}",
            ))

    # Check for running processes
    _check_running_processes(result)

    # If extension is linked and server exists, mark as healthy
    result.connected = result.configured
    result.healthy = result.configured

    return result


def check_codex_mcp(verbose: bool = False) -> HealthCheckResult:
    """Check MCP status in Codex.

    Codex uses config.toml for MCP configuration with TOML format:
    [mcp_servers.spellbook]
    command = "python3"
    args = ["/path/to/server.py"]
    """
    result = HealthCheckResult(healthy=False, platform="codex")

    config_dir = Path.home() / ".codex"
    config_toml = config_dir / "config.toml"

    # Get spellbook directory from env or script location
    spellbook_dir = Path(os.environ.get(
        "SPELLBOOK_DIR",
        str(Path(__file__).parent.parent)
    ))

    # Check if config directory exists
    if not config_dir.exists():
        result.error = "~/.codex directory not found"
        result.diagnostics.append(DiagnosticResult(
            check="config_dir_exists",
            passed=False,
            message="Codex config directory not found",
            details={"path": str(config_dir), "suggestion": "Install Codex or create ~/.codex"},
        ))
        return result

    result.diagnostics.append(DiagnosticResult(
        check="config_dir_exists",
        passed=True,
        message=f"Config directory exists: {config_dir}",
    ))

    # Check if config.toml exists
    if not config_toml.exists():
        result.configured = False
        result.error = "config.toml not found"
        result.diagnostics.append(DiagnosticResult(
            check="config_toml_exists",
            passed=False,
            message="config.toml not found",
            details={"path": str(config_toml), "suggestion": "Run the spellbook installer"},
        ))
        return result

    result.diagnostics.append(DiagnosticResult(
        check="config_toml_exists",
        passed=True,
        message=f"config.toml exists: {config_toml}",
    ))

    # Read and parse config.toml
    try:
        content = config_toml.read_text(encoding="utf-8")
    except OSError as e:
        result.error = f"Cannot read config.toml: {e}"
        result.diagnostics.append(DiagnosticResult(
            check="config_readable",
            passed=False,
            message=f"Cannot read config.toml: {e}",
        ))
        return result

    # Check for spellbook MCP section
    # Look for [mcp_servers.spellbook] or the demarcated section
    toml_marker = "# SPELLBOOK:START"
    has_spellbook = "[mcp_servers.spellbook]" in content or toml_marker in content

    if has_spellbook:
        result.configured = True
        result.diagnostics.append(DiagnosticResult(
            check="mcp_configured",
            passed=True,
            message="Spellbook MCP server is configured in config.toml",
        ))

        # Try to extract the server path from config
        # Pattern: args = ["/path/to/server.py"]
        args_match = re.search(r'args\s*=\s*\["([^"]+)"', content)
        if args_match:
            server_path = Path(args_match.group(1))
            if server_path.exists():
                result.diagnostics.append(DiagnosticResult(
                    check="server_script_exists",
                    passed=True,
                    message=f"Server script exists: {server_path}",
                ))
            else:
                result.healthy = False
                result.diagnostics.append(DiagnosticResult(
                    check="server_script_exists",
                    passed=False,
                    message=f"Server script not found: {server_path}",
                    details={"suggestion": "Re-run the spellbook installer"},
                ))
                return result
    else:
        result.configured = False
        result.error = "Spellbook MCP not configured in config.toml"
        result.diagnostics.append(DiagnosticResult(
            check="mcp_configured",
            passed=False,
            message="Spellbook MCP server not found in config.toml",
            details={"suggestion": "Run the spellbook installer: uv run install.py"},
        ))
        return result

    # Check for AGENTS.md
    agents_md = config_dir / "AGENTS.md"
    if agents_md.exists():
        content = agents_md.read_text(encoding="utf-8")
        if "SPELLBOOK" in content:
            result.diagnostics.append(DiagnosticResult(
                check="agents_md",
                passed=True,
                message="AGENTS.md contains spellbook section",
            ))
        else:
            result.diagnostics.append(DiagnosticResult(
                check="agents_md",
                passed=False,
                message="AGENTS.md exists but missing spellbook section",
            ))
    else:
        result.diagnostics.append(DiagnosticResult(
            check="agents_md",
            passed=False,
            message="AGENTS.md not found",
            details={"suggestion": "Run the spellbook installer"},
        ))

    # Check for running processes
    _check_running_processes(result)

    # If configured and server exists, mark as healthy
    result.connected = result.configured
    result.healthy = result.configured

    return result


def check_opencode_mcp(verbose: bool = False) -> HealthCheckResult:
    """Check MCP status in OpenCode.

    OpenCode uses opencode.json for MCP configuration with JSON format:
    {
        "mcp": {
            "spellbook": {
                "type": "local",
                "command": ["python3", "/path/to/server.py"],
                "enabled": true
            }
        }
    }
    """
    result = HealthCheckResult(healthy=False, platform="opencode")

    config_dir = Path.home() / ".config" / "opencode"
    config_json = config_dir / "opencode.json"

    # Get spellbook directory from env or script location
    spellbook_dir = Path(os.environ.get(
        "SPELLBOOK_DIR",
        str(Path(__file__).parent.parent)
    ))

    # Check if config directory exists
    if not config_dir.exists():
        result.error = "~/.config/opencode directory not found"
        result.diagnostics.append(DiagnosticResult(
            check="config_dir_exists",
            passed=False,
            message="OpenCode config directory not found",
            details={"path": str(config_dir), "suggestion": "Install OpenCode or create ~/.config/opencode"},
        ))
        return result

    result.diagnostics.append(DiagnosticResult(
        check="config_dir_exists",
        passed=True,
        message=f"Config directory exists: {config_dir}",
    ))

    # Check if opencode.json exists
    if not config_json.exists():
        result.configured = False
        result.error = "opencode.json not found"
        result.diagnostics.append(DiagnosticResult(
            check="config_json_exists",
            passed=False,
            message="opencode.json not found",
            details={"path": str(config_json), "suggestion": "Run the spellbook installer"},
        ))
        return result

    result.diagnostics.append(DiagnosticResult(
        check="config_json_exists",
        passed=True,
        message=f"opencode.json exists: {config_json}",
    ))

    # Read and parse opencode.json
    try:
        content = config_json.read_text(encoding="utf-8")
        config = json.loads(content)
    except json.JSONDecodeError as e:
        result.error = f"Invalid JSON in opencode.json: {e}"
        result.diagnostics.append(DiagnosticResult(
            check="config_valid_json",
            passed=False,
            message=f"opencode.json is not valid JSON: {e}",
        ))
        return result
    except OSError as e:
        result.error = f"Cannot read opencode.json: {e}"
        result.diagnostics.append(DiagnosticResult(
            check="config_readable",
            passed=False,
            message=f"Cannot read opencode.json: {e}",
        ))
        return result

    # Check for spellbook in mcp section
    mcp_config = config.get("mcp", {})
    spellbook_config = mcp_config.get("spellbook")

    if spellbook_config:
        result.configured = True
        result.diagnostics.append(DiagnosticResult(
            check="mcp_configured",
            passed=True,
            message="Spellbook MCP server is configured in opencode.json",
            details={"config": spellbook_config},
        ))

        # Check if enabled
        if spellbook_config.get("enabled", True):
            result.diagnostics.append(DiagnosticResult(
                check="mcp_enabled",
                passed=True,
                message="Spellbook MCP is enabled",
            ))
        else:
            result.diagnostics.append(DiagnosticResult(
                check="mcp_enabled",
                passed=False,
                message="Spellbook MCP is disabled in config",
                details={"suggestion": "Set 'enabled': true in opencode.json"},
            ))

        # Check server path from command
        command = spellbook_config.get("command", [])
        if len(command) >= 2:
            server_path = Path(command[-1])  # Last arg should be the script path
            if server_path.exists():
                result.diagnostics.append(DiagnosticResult(
                    check="server_script_exists",
                    passed=True,
                    message=f"Server script exists: {server_path}",
                ))
            else:
                result.healthy = False
                result.diagnostics.append(DiagnosticResult(
                    check="server_script_exists",
                    passed=False,
                    message=f"Server script not found: {server_path}",
                    details={"suggestion": "Re-run the spellbook installer"},
                ))
                return result
    else:
        result.configured = False
        result.error = "Spellbook MCP not configured in opencode.json"
        result.diagnostics.append(DiagnosticResult(
            check="mcp_configured",
            passed=False,
            message="Spellbook MCP server not found in opencode.json",
            details={"suggestion": "Run the spellbook installer: uv run install.py"},
        ))
        return result

    # Check for AGENTS.md
    agents_md = config_dir / "AGENTS.md"
    if agents_md.exists():
        content = agents_md.read_text(encoding="utf-8")
        if "SPELLBOOK" in content:
            result.diagnostics.append(DiagnosticResult(
                check="agents_md",
                passed=True,
                message="AGENTS.md contains spellbook section",
            ))
        else:
            result.diagnostics.append(DiagnosticResult(
                check="agents_md",
                passed=False,
                message="AGENTS.md exists but missing spellbook section",
            ))
    else:
        result.diagnostics.append(DiagnosticResult(
            check="agents_md",
            passed=False,
            message="AGENTS.md not found",
            details={"suggestion": "Run the spellbook installer"},
        ))

    # Check for running processes
    _check_running_processes(result)

    # If configured, enabled, and server exists, mark as healthy
    result.connected = result.configured
    result.healthy = result.configured and spellbook_config.get("enabled", True)

    return result


def get_check_function(platform: str):
    """Get the check function for a platform."""
    check_functions = {
        "claude": check_claude_mcp,
        "gemini": check_gemini_mcp,
        "codex": check_codex_mcp,
        "opencode": check_opencode_mcp,
    }
    return check_functions.get(platform, check_claude_mcp)


def get_config_check_function(platform: str):
    """Get the fast config-only check function for a platform."""
    # For most platforms, the check function is already fast
    # Only Claude has a separate slow (mcp list) vs fast (mcp get) check
    config_functions = {
        "claude": check_claude_config_only,
        "gemini": check_gemini_mcp,  # Already fast
        "codex": check_codex_mcp,  # Already fast
        "opencode": check_opencode_mcp,  # Already fast
    }
    return config_functions.get(platform, check_claude_config_only)


def wait_for_health(
    platform: str,
    timeout: float = 30.0,
    initial_delay: float = 1.0,
    max_delay: float = 5.0,
    verbose: bool = False,
) -> HealthCheckResult:
    """Wait for MCP to become healthy with exponential backoff."""
    start_time = time.time()
    delay = initial_delay
    attempt = 0

    check_fn = get_check_function(platform)

    while True:
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            result = check_fn(verbose=verbose)
            result.error = f"Timeout after {timeout}s ({attempt} attempts): {result.error or 'unknown'}"
            return result

        attempt += 1
        if verbose:
            print(f"Attempt {attempt}: checking {platform} MCP health...", file=sys.stderr)

        result = check_fn(verbose=verbose)

        if result.healthy:
            if verbose:
                print(f"MCP healthy after {elapsed:.1f}s", file=sys.stderr)
            return result

        if verbose:
            print(f"  Not healthy: {result.error}", file=sys.stderr)

        # Calculate next delay with exponential backoff
        remaining = timeout - (time.time() - start_time)
        if remaining <= 0:
            result.error = f"Timeout after {timeout}s ({attempt} attempts): {result.error or 'unknown'}"
            return result

        sleep_time = min(delay, remaining, max_delay)
        if verbose:
            print(f"  Retrying in {sleep_time:.1f}s...", file=sys.stderr)
        time.sleep(sleep_time)
        delay = min(delay * 2, max_delay)


def detect_platform() -> str:
    """Auto-detect which platform to check based on available CLIs and config dirs."""
    # Check CLIs first
    if shutil.which("claude"):
        return "claude"
    if shutil.which("gemini"):
        return "gemini"

    # Check config directories
    if (Path.home() / ".codex").exists():
        return "codex"
    if (Path.home() / ".config" / "opencode").exists():
        return "opencode"
    if (Path.home() / ".gemini").exists():
        return "gemini"

    return "claude"  # Default


def get_available_platforms() -> list[str]:
    """Get list of platforms that appear to be installed."""
    available = []

    if shutil.which("claude") or (Path.home() / ".claude").exists():
        available.append("claude")
    if shutil.which("gemini") or (Path.home() / ".gemini").exists():
        available.append("gemini")
    if (Path.home() / ".codex").exists():
        available.append("codex")
    if (Path.home() / ".config" / "opencode").exists():
        available.append("opencode")

    return available


def format_result(result: HealthCheckResult, verbose: bool = False) -> str:
    """Format the result for human-readable output."""
    lines = []

    status_icon = "✓" if result.healthy else "✗"
    lines.append(f"{status_icon} Spellbook MCP ({result.platform})")
    lines.append(f"  Healthy: {result.healthy}")
    lines.append(f"  Connected: {result.connected}")
    lines.append(f"  Configured: {result.configured}")
    lines.append(f"  Process Running: {result.process_running}")

    if result.error:
        lines.append(f"  Error: {result.error}")

    if verbose and result.diagnostics:
        lines.append("\nDiagnostics:")
        for diag in result.diagnostics:
            icon = "✓" if diag.passed else "✗"
            lines.append(f"  {icon} {diag.check}: {diag.message}")
            if diag.details:
                for key, value in diag.details.items():
                    if isinstance(value, str) and "\n" in value:
                        lines.append(f"      {key}:")
                        for line in value.split("\n"):
                            lines.append(f"        {line}")
                    else:
                        lines.append(f"      {key}: {value}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Check spellbook MCP server health in coding assistants",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--platform", "-p",
        choices=["claude", "gemini", "codex", "opencode", "auto", "all"],
        default="auto",
        help="Platform to check (default: auto-detect, 'all' checks all installed)",
    )
    parser.add_argument(
        "--wait", "-w",
        action="store_true",
        help="Wait for server to become healthy with exponential backoff",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=float,
        default=30.0,
        help="Timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--config-only", "-c",
        action="store_true",
        help="Only check configuration files (fast, no connection test)",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output result as JSON",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output with diagnostics",
    )

    args = parser.parse_args()

    try:
        # Handle --platform all
        if args.platform == "all":
            platforms = get_available_platforms()
            if not platforms:
                platforms = ["claude"]  # Default if nothing found

            results = []
            all_healthy = True

            for platform in platforms:
                if args.config_only:
                    check_fn = get_config_check_function(platform)
                elif args.wait:
                    result = wait_for_health(
                        platform=platform,
                        timeout=args.timeout,
                        verbose=args.verbose,
                    )
                    results.append(result)
                    if not result.healthy:
                        all_healthy = False
                    continue
                else:
                    check_fn = get_check_function(platform)

                result = check_fn(verbose=args.verbose)
                results.append(result)
                if not result.healthy:
                    all_healthy = False

            if args.json:
                print(json.dumps({
                    "healthy": all_healthy,
                    "platforms": [r.to_dict() for r in results],
                }, indent=2))
            else:
                for result in results:
                    print(format_result(result, verbose=args.verbose))
                    print()

            sys.exit(0 if all_healthy else 1)

        # Single platform check
        platform = args.platform if args.platform != "auto" else detect_platform()

        if args.config_only:
            check_fn = get_config_check_function(platform)
            result = check_fn(verbose=args.verbose)
        elif args.wait:
            result = wait_for_health(
                platform=platform,
                timeout=args.timeout,
                verbose=args.verbose,
            )
        else:
            check_fn = get_check_function(platform)
            result = check_fn(verbose=args.verbose)

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(format_result(result, verbose=args.verbose))

        sys.exit(0 if result.healthy else 1)

    except KeyboardInterrupt:
        if args.json:
            print(json.dumps({"healthy": False, "error": "Interrupted"}))
        else:
            print("\nInterrupted", file=sys.stderr)
        sys.exit(130)

    except Exception as e:
        if args.json:
            print(json.dumps({"healthy": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
