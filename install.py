#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Spellbook Installer - Self-bootstrapping multi-platform AI assistant skills installation.

This script can be run directly or via curl-pipe. It will:
1. Install uv (Python package manager) if missing
2. Re-execute itself under uv to ensure correct Python version
3. Clone the spellbook repository if not already in one
4. Install skills for selected platforms

Usage:
    # From curl (installs everything):
    curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/install.py | python3

    # From repo (already cloned):
    python3 install.py
    uv run install.py

    # Non-interactive with defaults:
    python3 install.py --yes

Options:
    --yes, -y           Accept all defaults without prompting
    --install-dir DIR   Install spellbook to DIR (default: ~/.local/share/spellbook)
    --platforms LIST    Comma-separated platforms (claude_code,opencode,codex,gemini)
    --force             Reinstall even if version matches
    --dry-run           Show what would be done without making changes
    --verify-mcp        Verify MCP server connectivity after installation
    --no-interactive    Skip platform selection UI
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

# =============================================================================
# Constants
# =============================================================================

DEFAULT_INSTALL_DIR = Path.home() / ".local" / "share" / "spellbook"
REPO_URL = "https://github.com/axiomantic/spellbook.git"
MIN_PYTHON_VERSION = (3, 10)

# ANSI colors (only used if terminal supports them)
class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    BOLD = "\033[1m"
    NC = "\033[0m"


def supports_color() -> bool:
    """Check if terminal supports colors."""
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if os.environ.get("NO_COLOR"):
        return False
    return True


def color(text: str, color_code: str) -> str:
    """Apply color if supported."""
    if supports_color():
        return f"{color_code}{text}{Colors.NC}"
    return text


def print_header() -> None:
    """Print installation header."""
    print()
    print(color("=" * 60, Colors.CYAN))
    print(color("  Spellbook Installer", Colors.CYAN))
    print(color("=" * 60, Colors.CYAN))
    print()


def print_step(msg: str) -> None:
    print(f"{color('>', Colors.BLUE)} {msg}")


def print_success(msg: str) -> None:
    print(f"{color('[ok]', Colors.GREEN)} {msg}")


def print_error(msg: str) -> None:
    print(f"{color('[error]', Colors.RED)} {msg}", file=sys.stderr)


def print_warning(msg: str) -> None:
    print(f"{color('[!]', Colors.YELLOW)} {msg}")


def print_info(msg: str) -> None:
    print(f"    {msg}")


# =============================================================================
# Interactive Prompts
# =============================================================================

def is_interactive() -> bool:
    """Check if we're running interactively."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def prompt_yn(prompt: str, default: bool = True, auto_yes: bool = False) -> bool:
    """Prompt for yes/no confirmation."""
    if auto_yes or not is_interactive():
        return default

    yn = "[Y/n]" if default else "[y/N]"
    try:
        response = input(f"{color(prompt, Colors.BOLD)} {yn} ").strip().lower()
        if not response:
            return default
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


# =============================================================================
# OS Detection
# =============================================================================

def detect_os() -> str:
    """Detect operating system."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    elif system == "windows":
        return "windows"
    return "unknown"


def detect_distro() -> str:
    """Detect Linux distribution."""
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    return line.strip().split("=")[1].strip('"')
    except FileNotFoundError:
        pass

    if Path("/etc/debian_version").exists():
        return "debian"
    if Path("/etc/redhat-release").exists():
        return "rhel"
    return "unknown"


# =============================================================================
# Prerequisite Checks and Installation
# =============================================================================

def check_command(cmd: str) -> bool:
    """Check if a command is available."""
    return shutil.which(cmd) is not None


def check_uv() -> bool:
    """Check if uv is available."""
    if check_command("uv"):
        return True

    # Check common install locations
    for path in [
        Path.home() / ".local" / "bin" / "uv",
        Path.home() / ".cargo" / "bin" / "uv",
    ]:
        if path.is_file() and os.access(path, os.X_OK):
            # Add to PATH for this session
            os.environ["PATH"] = f"{path.parent}:{os.environ.get('PATH', '')}"
            return True

    return False


def install_uv(auto_yes: bool = False) -> bool:
    """Install uv package manager."""
    print_step("uv (Python package manager) is required but not installed.")
    print_info("uv is a fast Python package manager from Astral.")
    print_info("Learn more: https://docs.astral.sh/uv/")
    print()

    if not prompt_yn("Install uv?", default=True, auto_yes=auto_yes):
        print_error("uv is required. Install it manually:")
        print_info("curl -LsSf https://astral.sh/uv/install.sh | sh")
        return False

    print_step("Installing uv...")
    try:
        result = subprocess.run(
            ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print_error(f"Failed to install uv: {result.stderr}")
            return False

        # Add to PATH
        os.environ["PATH"] = f"{Path.home()}/.local/bin:{os.environ.get('PATH', '')}"
        print_success("uv installed successfully")
        return True

    except Exception as e:
        print_error(f"Failed to install uv: {e}")
        return False


def check_git() -> bool:
    """Check if git is available."""
    return check_command("git")


def install_git_instructions() -> None:
    """Print git installation instructions."""
    os_type = detect_os()
    distro = detect_distro()

    print_step("Git is required but not installed.")
    print()

    if os_type == "macos":
        print_info("On macOS, install Xcode Command Line Tools:")
        print_info("  xcode-select --install")
    elif os_type == "linux":
        if distro in ("ubuntu", "debian", "pop"):
            print_info("  sudo apt update && sudo apt install -y git")
        elif distro == "fedora":
            print_info("  sudo dnf install -y git")
        elif distro in ("arch", "manjaro"):
            print_info("  sudo pacman -S git")
        else:
            print_info("  Use your distribution's package manager to install git")
    else:
        print_info("Please install git and try again.")


def install_git(auto_yes: bool = False) -> bool:
    """Attempt to install git."""
    os_type = detect_os()
    distro = detect_distro()

    install_git_instructions()
    print()

    if os_type == "macos":
        if prompt_yn("Install Xcode Command Line Tools (includes git)?", auto_yes=auto_yes):
            print_step("Installing Xcode Command Line Tools...")
            subprocess.run(["xcode-select", "--install"], check=False)
            print_warning("A dialog should appear. After installation, run this script again.")
            return False

    elif os_type == "linux":
        if not prompt_yn("Attempt automatic installation?", auto_yes=auto_yes):
            return False

        try:
            if distro in ("ubuntu", "debian", "pop"):
                subprocess.run(["sudo", "apt", "update"], check=True)
                subprocess.run(["sudo", "apt", "install", "-y", "git"], check=True)
            elif distro == "fedora":
                subprocess.run(["sudo", "dnf", "install", "-y", "git"], check=True)
            elif distro in ("arch", "manjaro"):
                subprocess.run(["sudo", "pacman", "-S", "--noconfirm", "git"], check=True)
            else:
                print_error(f"Automatic installation not supported for {distro}")
                return False

            print_success("git installed")
            return True

        except subprocess.CalledProcessError as e:
            print_error(f"Failed to install git: {e}")
            return False

    return False


def check_python_version() -> bool:
    """Check if Python version meets minimum requirements."""
    return sys.version_info >= MIN_PYTHON_VERSION


def running_under_uv() -> bool:
    """Check if we're running under uv (in a uv-managed environment)."""
    # uv sets VIRTUAL_ENV when running scripts
    if os.environ.get("VIRTUAL_ENV"):
        venv_path = os.environ["VIRTUAL_ENV"]
        # uv environments are in ~/.cache/uv/
        if ".cache/uv" in venv_path or "uv" in venv_path:
            return True

    # Check if uv python was used directly
    if "uv" in sys.executable.lower():
        return True

    return False


# =============================================================================
# Repository Management
# =============================================================================

def check_repo_needs_update(repo_dir: Path, timeout: int = 30) -> tuple[bool | None, str | None]:
    """
    Check if a git repo is behind its remote.

    Performs a git fetch and compares local HEAD to upstream.

    Args:
        repo_dir: Path to the git repository
        timeout: Timeout for git fetch in seconds

    Returns:
        (needs_update, reason) where:
        - (True, "N commits behind origin/main") if updates available
        - (False, None) if already up to date
        - (None, "error message") if check failed (network, etc.)
    """
    try:
        # Fetch from remote (quiet, with timeout)
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "fetch", "--quiet"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return (None, f"git fetch failed: {result.stderr.strip()}")

        # Get the default branch from remote HEAD
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            # refs/remotes/origin/HEAD -> refs/remotes/origin/main
            remote_ref = result.stdout.strip()
        else:
            # Fallback: try origin/main, then origin/master
            for branch in ["origin/main", "origin/master"]:
                result = subprocess.run(
                    ["git", "-C", str(repo_dir), "rev-parse", "--verify", branch],
                    capture_output=True,
                )
                if result.returncode == 0:
                    remote_ref = branch
                    break
            else:
                return (None, "could not determine remote branch")

        # Count commits we're behind
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-list", "--count", f"HEAD..{remote_ref}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return (None, f"could not compare versions: {result.stderr.strip()}")

        behind_count = int(result.stdout.strip())

        if behind_count > 0:
            # Extract just the branch name for the message
            branch_name = remote_ref.split("/")[-1] if "/" in remote_ref else remote_ref
            return (True, f"{behind_count} commit{'s' if behind_count > 1 else ''} behind {branch_name}")
        else:
            return (False, None)

    except subprocess.TimeoutExpired:
        return (None, "git fetch timed out (network issue?)")
    except ValueError as e:
        return (None, f"unexpected git output: {e}")
    except Exception as e:
        return (None, f"error checking for updates: {e}")


def is_spellbook_repo(path: Path) -> bool:
    """Check if a path is a spellbook repository."""
    # Key indicators of spellbook repo
    return (
        (path / "skills").is_dir()
        and (path / "CLAUDE.spellbook.md").is_file()
    )


def is_running_from_pipe() -> bool:
    """Check if script is being run from a pipe (curl | python3)."""
    try:
        # When piped, __file__ is typically '<stdin>' or similar
        return not Path(__file__).resolve().exists()
    except (OSError, ValueError):
        return True


def find_spellbook_dir() -> Path | None:
    """Find spellbook directory, walking up from current/script location."""
    # If running from pipe, we can't check script location
    if not is_running_from_pipe():
        # First check from script location
        try:
            script_dir = Path(__file__).resolve().parent
            for _ in range(10):
                if is_spellbook_repo(script_dir):
                    return script_dir
                parent = script_dir.parent
                if parent == script_dir:
                    break
                script_dir = parent
        except (OSError, ValueError):
            pass

    # Then check from current directory
    cwd = Path.cwd()
    for _ in range(10):
        if is_spellbook_repo(cwd):
            return cwd
        parent = cwd.parent
        if parent == cwd:
            break
        cwd = parent

    # Check default install location
    if is_spellbook_repo(DEFAULT_INSTALL_DIR):
        return DEFAULT_INSTALL_DIR

    return None


def clone_repository(install_dir: Path, auto_yes: bool = False) -> bool:
    """Clone the spellbook repository."""
    if install_dir.exists():
        if (install_dir / ".git").is_dir():
            print_info(f"Found existing installation at {install_dir}")

            # Check if updates are available before prompting
            print_step("Checking for updates...")
            needs_update, reason = check_repo_needs_update(install_dir)

            if needs_update is None:
                # Check failed (network issue, etc.)
                print_warning(f"Could not check for updates: {reason}")
                print_info("Continuing with existing version.")
                return True
            elif needs_update is False:
                # Already up to date
                print_success("Already at latest version")
                return True
            else:
                # Updates available
                print_info(f"Updates available: {reason}")

                # In headless/non-interactive mode, auto-update
                # In interactive mode, prompt user
                should_update = auto_yes or not is_interactive()
                if not should_update:
                    should_update = prompt_yn("Update to latest version?", auto_yes=False)

                if should_update:
                    print_step("Updating repository...")
                    try:
                        subprocess.run(
                            ["git", "-C", str(install_dir), "pull", "--ff-only"],
                            check=True,
                            capture_output=True,
                        )
                        print_success("Updated to latest version")
                    except subprocess.CalledProcessError:
                        print_warning("Could not fast-forward. Using existing version.")
                else:
                    print_info("Skipping update, using existing version.")
                return True
        else:
            print_warning(f"Directory {install_dir} exists but is not a git repository.")
            if prompt_yn("Back up and replace?", auto_yes=auto_yes):
                import time
                backup = install_dir.with_name(f"{install_dir.name}.backup.{int(time.time())}")
                install_dir.rename(backup)
                print_info(f"Backed up to {backup}")
            else:
                print_error("Cannot continue without a clean install directory.")
                return False

    print_step(f"Cloning spellbook to {install_dir}...")
    install_dir.parent.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            ["git", "clone", REPO_URL, str(install_dir)],
            check=True,
        )
        print_success("Repository cloned")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to clone repository: {e}")
        return False


# =============================================================================
# Self-Bootstrap Logic
# =============================================================================

def reexec_under_uv(script_path: Path | None, args: list[str]) -> NoReturn:
    """Re-execute this script under uv."""
    print_step("Re-executing under uv for dependency management...")

    if script_path and script_path.exists():
        cmd = ["uv", "run", str(script_path)] + args + ["--bootstrapped"]
    else:
        # Running from pipe - need to clone first, then run from repo
        # For now, just continue with bootstrapped flag since uv will handle Python
        print_info("Running from pipe, continuing with current Python...")
        # Don't re-exec, just return (caller should continue)
        return  # type: ignore

    os.execvp("uv", cmd)


def get_script_path() -> Path | None:
    """Get the path to this script, or None if running from pipe."""
    if is_running_from_pipe():
        return None
    try:
        path = Path(__file__).resolve()
        return path if path.exists() else None
    except (OSError, ValueError):
        return None


def bootstrap(args: argparse.Namespace) -> Path:
    """
    Bootstrap phase: ensure prerequisites and get spellbook directory.

    Returns the spellbook directory path.
    """
    auto_yes = args.yes

    # Step 1: Ensure uv is available
    if not args.bootstrapped:
        if not check_uv():
            if not install_uv(auto_yes):
                print_error("Cannot continue without uv.")
                sys.exit(1)

        # Re-exec under uv if we're not already (and not from pipe)
        script_path = get_script_path()
        if not running_under_uv() and script_path:
            # Pass through all original arguments
            original_args = sys.argv[1:]
            reexec_under_uv(script_path, original_args)
            # If we get here, reexec returned (pipe case) - continue normally

    # Step 2: Ensure git is available
    if not check_git():
        if not install_git(auto_yes):
            print_error("Cannot continue without git.")
            sys.exit(1)

    # Step 3: Find or clone spellbook repository
    spellbook_dir = find_spellbook_dir()

    if spellbook_dir:
        print_success(f"Found spellbook at {spellbook_dir}")
    else:
        # Need to clone
        install_dir = Path(args.install_dir) if args.install_dir else DEFAULT_INSTALL_DIR
        print_info(f"Spellbook repository not found.")

        if not clone_repository(install_dir, auto_yes):
            sys.exit(1)

        spellbook_dir = install_dir

        # Re-exec from the cloned repo to get the latest install.py
        # This handles the upgrade case: old cached install.py clones new repo
        new_script = spellbook_dir / "install.py"
        current_script = get_script_path()

        should_reexec = new_script.exists() and (
            current_script is None or  # Running from pipe
            new_script.resolve() != current_script.resolve()
        )

        if should_reexec:
            print_step("Running installer from cloned repository...")
            # Filter out --install-dir and its value
            filtered_args = []
            skip_next = False
            for arg in sys.argv[1:]:
                if skip_next:
                    skip_next = False
                    continue
                if arg == "--install-dir":
                    skip_next = True
                    continue
                if arg.startswith("--install-dir="):
                    continue
                if arg == "--bootstrapped":
                    continue
                filtered_args.append(arg)

            cmd = ["uv", "run", str(new_script)] + filtered_args
            os.execvp("uv", cmd)

    return spellbook_dir


# =============================================================================
# Main Installation Logic
# =============================================================================

def run_installation(spellbook_dir: Path, args: argparse.Namespace) -> int:
    """Run the actual installation after bootstrap."""
    # Add spellbook to path for imports
    sys.path.insert(0, str(spellbook_dir))

    # Import installer components
    try:
        from installer.core import Installer
        from installer.ui import (
            Spinner,
            print_directory_config,
            print_header as print_installer_header,
            print_info as installer_print_info,
            print_report,
            print_warning as installer_print_warning,
            print_success as installer_print_success,
        )
        from installer.components.mcp import verify_mcp_connectivity
    except ImportError as e:
        print_error(f"Failed to import installer components: {e}")
        print_info("Make sure you're running from a valid spellbook repository.")
        return 1

    installer = Installer(spellbook_dir)
    print_installer_header(installer.version)

    # Determine platforms to install
    if args.platforms:
        platforms = args.platforms.split(",")
    elif args.no_interactive or not is_interactive():
        platforms = installer.detect_platforms()
        installer_print_info(f"Auto-detected platforms: {', '.join(platforms)}")
        print()
    else:
        try:
            from installer.tui import interactive_platform_select

            platforms = interactive_platform_select()

            if platforms is None:
                installer_print_warning("Installation cancelled")
                return 1

            if not platforms:
                installer_print_warning("No platforms selected")
                return 1

        except (ImportError, Exception) as e:
            installer_print_warning(f"Interactive mode unavailable ({e}), using auto-detect")
            platforms = installer.detect_platforms()

    # Show directory configuration
    print_directory_config(spellbook_dir, platforms)

    if args.dry_run:
        installer_print_warning("DRY RUN - no changes will be made")
        print()

    with Spinner("Installing"):
        session = installer.run(
            platforms=platforms,
            force=args.force,
            dry_run=args.dry_run,
        )

    if args.verify_mcp and not args.dry_run:
        print()
        server_path = spellbook_dir / "spellbook_mcp" / "server.py"
        with Spinner("Verifying MCP server"):
            success, msg = verify_mcp_connectivity(server_path)
        if success:
            installer_print_success(f"MCP server: {msg}")
        else:
            installer_print_warning(f"MCP server: {msg}")

    print_report(session)

    # Show post-install instructions if interactive and not dry-run
    if not args.dry_run and is_interactive():
        try:
            from installer.tui import show_post_install_instructions
            show_post_install_instructions(session.platforms_installed)
        except ImportError:
            pass

    return 0 if session.success else 1


# =============================================================================
# Entry Point
# =============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install Spellbook - Multi-platform AI assistant skills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive install (recommended)
  python3 install.py

  # Non-interactive with defaults
  python3 install.py --yes

  # Curl-pipe install
  curl -fsSL .../install.py | python3 - --yes

  # Specific platforms only
  python3 install.py --platforms claude_code,codex
""",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Accept all defaults without prompting",
    )
    parser.add_argument(
        "--install-dir",
        type=str,
        default=None,
        help=f"Install spellbook to DIR (default: {DEFAULT_INSTALL_DIR})",
    )
    parser.add_argument(
        "--platforms",
        type=str,
        default=None,
        help="Comma-separated platforms (claude_code,opencode,codex,gemini)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reinstall even if version matches",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without changes",
    )
    parser.add_argument(
        "--verify-mcp",
        action="store_true",
        help="Verify MCP server connectivity",
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Skip interactive platform selection",
    )
    parser.add_argument(
        "--bootstrapped",
        action="store_true",
        help=argparse.SUPPRESS,  # Hidden flag - set after bootstrap phase
    )

    args = parser.parse_args()

    # Auto-enable --yes if not interactive
    if not is_interactive():
        args.yes = True

    print_header()

    # Bootstrap phase
    print_step("Checking prerequisites...")
    print()

    spellbook_dir = bootstrap(args)

    print()

    # Installation phase
    return run_installation(spellbook_dir, args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print_warning("Installation cancelled.")
        sys.exit(130)
