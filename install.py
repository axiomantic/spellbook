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
    --no-interactive    Skip platform selection UI
    --no-admin          Disable the web admin interface (enabled by default)
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
    """Print installation header with box-drawing characters."""
    title = "  Spellbook Installer"
    width = max(len(title) + 2, 50)
    line = "\u2500" * width
    print()
    print(f"\u250c{line}\u2510")
    print(f"\u2502{title:<{width}}\u2502")
    print(f"\u2514{line}\u2518")
    print()


def print_step(msg: str) -> None:
    icon = color("→", Colors.BLUE)
    print(f"  {icon} {msg}")


def print_success(msg: str) -> None:
    icon = color("✓", Colors.GREEN)
    print(f"  {icon} {msg}")


def print_error(msg: str) -> None:
    icon = color("✗", Colors.RED)
    print(f"  {icon} {msg}", file=sys.stderr)


def print_warning(msg: str) -> None:
    icon = color("⚠", Colors.YELLOW)
    print(f"  {icon} {msg}")


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
    """Detect operating system.

    Note: Intentionally duplicates installer.compat.get_platform() because
    install.py must work before dependencies are available (pre-bootstrap).
    """
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
            os.environ["PATH"] = f"{path.parent}{os.pathsep}{os.environ.get('PATH', '')}"
            return True

    return False


def _install_uv_windows() -> bool:
    """Install uv on Windows via PowerShell."""
    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command",
             "irm https://astral.sh/uv/install.ps1 | iex"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print_error(f"Failed to install uv: {result.stderr}")
            return False
        uv_found = shutil.which("uv")
        if uv_found:
            uv_path = Path(uv_found).parent
        else:
            # Guess common install locations if shutil.which fails
            uv_path = Path.home() / ".local" / "bin"
            if not uv_path.exists():
                uv_path = Path.home() / ".cargo" / "bin"
        os.environ["PATH"] = f"{uv_path}{os.pathsep}{os.environ.get('PATH', '')}"
        print_success("uv installed successfully")
        return True
    except Exception as e:
        print_error(f"Failed to install uv: {e}")
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

    os_type = detect_os()
    if os_type == "windows":
        return _install_uv_windows()

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
        os.environ["PATH"] = f"{Path.home() / '.local' / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"
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
    elif os_type == "windows":
        print_info("Install Git for Windows:")
        print_info("  winget install Git.Git")
        print_info("  or download from https://git-scm.com/download/win")
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
        and (path / "AGENTS.spellbook.md").is_file()
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

    if sys.platform == "win32":
        sys.exit(subprocess.call(cmd))
    else:
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
        # After re-exec, suppress status noise (Rich welcome panel will show)
        _quiet = args.bootstrapped
        if not _quiet:
            print_success(f"Found spellbook at {spellbook_dir}")

        # If running install.py from the source repo itself, skip the update check
        script_path = get_script_path()
        if script_path is not None and str(script_path).startswith(str(spellbook_dir.resolve())):
            print_info("Running from source repository, skipping update check.")
        elif (spellbook_dir / ".git").is_dir():
            if not _quiet:
                print_step("Checking for updates...")
            needs_update, reason = check_repo_needs_update(spellbook_dir)

            if needs_update is None:
                # Check failed (network issue, etc.)
                print_warning(f"Could not check for updates: {reason}")
            elif needs_update:
                print_info(f"Updates available: {reason}")

                # In headless/non-interactive mode, auto-update
                should_update = auto_yes or not is_interactive()
                if not should_update:
                    should_update = prompt_yn("Update to latest version?", auto_yes=False)

                if should_update:
                    print_step("Updating repository...")
                    try:
                        subprocess.run(
                            ["git", "-C", str(spellbook_dir), "pull", "--ff-only"],
                            check=True,
                            capture_output=True,
                        )
                        print_success("Updated to latest version")

                        # Re-exec from updated repo to use latest install.py
                        new_script = spellbook_dir / "install.py"
                        current_script = get_script_path()
                        if new_script.exists() and (
                            current_script is None or
                            new_script.resolve() != current_script.resolve()
                        ):
                            print_step("Running updated installer...")
                            filtered_args = [a for a in sys.argv[1:] if a != "--bootstrapped"]
                            cmd = ["uv", "run", str(new_script)] + filtered_args + ["--bootstrapped"]
                            if sys.platform == "win32":
                                sys.exit(subprocess.call(cmd))
                            else:
                                os.execvp("uv", cmd)
                    except subprocess.CalledProcessError:
                        print_warning("Could not fast-forward. Using existing version.")
            else:
                if not _quiet:
                    print_info("Already at latest version")
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
            if sys.platform == "win32":
                sys.exit(subprocess.call(cmd))
            else:
                os.execvp("uv", cmd)

    return spellbook_dir


# =============================================================================
# Optional TTS Setup
# =============================================================================


def check_tts_available() -> bool:
    """Check if Wyoming TTS server is reachable.

    Delegates to ``installer.utils.check_tts_available`` so that installer
    sub-modules can import the function without ``sys.path`` manipulation.
    Re-exported here for backward compatibility with existing callers and
    test patches that reference ``install.check_tts_available``.
    """
    from installer.utils import check_tts_available as _check
    return _check()


def _set_tts_config(enabled: bool) -> None:
    """Persist the tts_enabled config value via spellbook config_tools."""
    try:
        from spellbook.core.config import config_set as _cfg_set
        _cfg_set("tts_enabled", enabled)
    except ImportError:
        pass



def setup_tts(
    dry_run: bool = False,
    auto_yes: bool = False,
    spellbook_dir: Path | None = None,
) -> None:
    """Offer to enable TTS.

    Skipped during dry-run or if user already configured TTS previously.
    Checks if a Wyoming TTS server is reachable and asks to enable.
    """
    if dry_run:
        return

    # Check if user already made a TTS decision (don't re-prompt on reinstall)
    try:
        from spellbook.core.config import config_get as _cfg_get
        existing = _cfg_get("tts_enabled")
        if existing is not None:
            if check_tts_available():
                print_info(f"TTS already configured (enabled={existing})")
                return
    except ImportError:
        pass

    print()
    if check_tts_available():
        # Wyoming server reachable, ask to enable
        enabled = prompt_yn(
            "Wyoming TTS server detected. Enable text-to-speech notifications?",
            default=True,
            auto_yes=auto_yes,
        )
        _set_tts_config(enabled)
        if enabled:
            print_success("TTS enabled")
            print_info("Change settings with tts_session_set or tts_config_set MCP tools")
        else:
            print_info("TTS disabled. Enable later with tts_config_set MCP tool")
    else:
        # Server not reachable, inform user
        enabled = prompt_yn(
            "Enable text-to-speech notifications? (Requires a Wyoming TTS server)",
            default=False,
            auto_yes=False,  # Never auto-enable when server not available
        )
        _set_tts_config(enabled)
        if enabled:
            print_info("TTS enabled. Start a Wyoming TTS server (e.g., wyoming-piper) on localhost:10200")
        else:
            print_info("TTS skipped. Enable later with tts_config_set MCP tool")


def _run_tts_setup(
    dry_run: bool,
    auto_yes: bool,
    spellbook_dir: Path,
    live_display=None,
) -> bool:
    """TTS setup integrated with LiveProgressDisplay.

    Returns True if any TTS steps were added to the display.
    """
    if dry_run:
        return False

    try:
        from spellbook.core.config import config_get as _cfg_get
        existing = _cfg_get("tts_enabled")
    except (ImportError, Exception):
        existing = None

    if existing is None:
        # First install: TTS choice handled by interactive setup_tts after progress
        if live_display:
            live_display.add_step("TTS: not yet configured (skip)")
            live_display.complete_step(success=True)
        return True

    if existing is False:
        if live_display:
            live_display.add_step("TTS: disabled by user")
            live_display.complete_step(success=True)
        return True

    # TTS is enabled - check if Wyoming server is reachable
    if check_tts_available():
        if live_display:
            live_display.add_step("TTS: available")
            live_display.complete_step(success=True)
        else:
            print_info("TTS already configured (enabled=True)")
        return True

    # TTS enabled but server not reachable
    if live_display:
        live_display.add_step("TTS: enabled but Wyoming server not reachable")
        live_display.complete_step(success=False)
    else:
        print_warning("TTS enabled but Wyoming server not reachable at configured host:port")
    return True


# =============================================================================
# Upgrade Awareness
# =============================================================================

def show_whats_new(spellbook_dir: Path, previous_version: str | None, current_version: str) -> None:
    """Show changelog entries between the previous and current version on upgrade."""
    if not previous_version or previous_version == current_version:
        return

    try:
        from installer.version import get_changelog_between_versions

        changelog_path = spellbook_dir / "CHANGELOG.md"
        entries = get_changelog_between_versions(changelog_path, previous_version, current_version)
        if not entries:
            return

        print()
        print(color("  WHAT'S NEW", Colors.BOLD))
        print(f"  {previous_version} → {current_version}")
        print()
        for line in entries.splitlines():
            # Indent changelog content for visual nesting
            if line.startswith("### "):
                # Section headers (Added, Fixed, Changed)
                print(f"  {color(line[4:], Colors.CYAN)}")
            elif line.startswith("- "):
                print(f"    {line}")
            elif line.startswith("  "):
                print(f"    {line}")
            elif line.strip():
                print(f"    {line}")
        print()
    except Exception as e:
        print(f"\nWarning: Could not display changelog updates: {e}")


def show_admin_info(admin_enabled: bool) -> None:
    """Show information about the admin web interface."""
    print()
    if admin_enabled:
        print(f"  {color('Admin Web Interface', Colors.BOLD)}")
        print(f"    Status: {color('enabled', Colors.GREEN)}")
        print(f"    URL:    http://localhost:8765/admin")
        print(f"    Open:   spellbook admin open")
        print(f"    Disable: set admin_enabled=false in spellbook.json or reinstall with --no-admin")
    else:
        print(f"  {color('Admin Web Interface', Colors.BOLD)}")
        print(f"    Status: {color('disabled', Colors.YELLOW)}")
        print(f"    Enable: set admin_enabled=true in spellbook.json or reinstall without --no-admin")
    print()


# =============================================================================
# Main Installation Logic
# =============================================================================

def run_installation(spellbook_dir: Path, args: argparse.Namespace) -> int:
    """Run the actual installation after bootstrap."""
    # Add spellbook to path for imports
    sys.path.insert(0, str(spellbook_dir))

    # Import installer components
    try:
        from installer.config import PLATFORM_CONFIG
        from installer.core import Installer
        from installer.ui import (
            InstallTimer,
            Spinner,
            color as installer_color,
            Colors as InstallerColors,
            print_directory_config,
            print_header as print_installer_header,
            print_info as installer_print_info,
            print_platform_section,
            print_report,
            print_result,
            print_step,
            print_warning as installer_print_warning,
            print_success as installer_print_success,
        )
    except ImportError as e:
        print_error(f"Failed to import installer components: {e}")
        print_info("Make sure you're running from a valid spellbook repository.")
        return 1

    installer = Installer(spellbook_dir)

    # Create renderer (Rich for TTY, plain text otherwise)
    try:
        from installer.renderer import PlainTextRenderer, RichRenderer
        if sys.stdout.isatty():
            renderer = RichRenderer(auto_yes=args.yes)
        else:
            renderer = PlainTextRenderer(auto_yes=args.yes)
    except ImportError:
        # Fallback: renderer module not available (should not happen normally)
        renderer = None

    # Handle --reconfigure: run config wizard for unset keys only
    if args.reconfigure:
        from spellbook.core.config import config_set, get_unset_config_keys
        unset_keys = get_unset_config_keys()
        if unset_keys and renderer is not None:
            selections = renderer.render_config_wizard(unset_keys, {}, is_upgrade=False)
            if selections:
                for key, value in selections.items():
                    config_set(key, value)
        elif not unset_keys:
            print_success("All config keys are already set.")

        # Offer profile selection during reconfigure
        if renderer is not None:
            profile_config = renderer.render_profile_wizard(reconfigure=True)
            if "profile.default" in profile_config:
                config_set("profile.default", profile_config["profile.default"])
        return 0

    is_upgrade = False  # Will be refined after installer.run() returns

    if renderer is not None:
        renderer.render_welcome(version=installer.version, is_upgrade=is_upgrade)
    else:
        print_installer_header(installer.version)

    # Build config_dir_overrides from per-platform CLI flags
    config_dir_overrides: dict[str, list[Path]] = {}
    for platform_id in PLATFORM_CONFIG:
        cli_dirs = getattr(args, f"{platform_id}_config_dirs", None)
        if cli_dirs:
            config_dir_overrides[platform_id] = [Path(d) for d in cli_dirs]

    from installer.tui import get_feature_groups as _get_fg
    from installer.wizard import WizardContext, WizardResults, _matches_unset_key

    # Import config module early; may fail in bootstrap scenarios
    try:
        from spellbook.core.config import (
            config_get as _cfg_get_early,
            config_is_explicitly_set as _cfg_is_set,
        )
        _config_available = True
    except ImportError:
        _config_available = False
        _cfg_get_early = None  # type: ignore[assignment]
        _cfg_is_set = None  # type: ignore[assignment]

    def _get_all_security_keys() -> list[str]:
        """Return dotted config keys for all security features."""
        return [
            f"security.{f['id']}.enabled"
            for group in _get_fg()
            for f in group["features"]
        ]

    def _get_unset_security_keys(all_keys: list[str]) -> list[str]:
        """Return security config keys that have not been explicitly set."""
        if not _config_available:
            return all_keys
        return [k for k in all_keys if not _cfg_is_set(k)]

    def _get_default_security_selections(unset_keys: list[str]) -> dict[str, bool]:
        """Return default security selections for any unset config keys.

        Looks up the recommended default for each feature whose config key
        appears in *unset_keys* and returns a ``{feature_id: default}`` dict.
        """
        selections: dict[str, bool] = {}
        for group in _get_fg():
            for feat in group["features"]:
                if _matches_unset_key(feat["id"], unset_keys):
                    selections[feat["id"]] = feat["default"]
        return selections

    # ---- Assemble WizardContext and run upfront wizard ----
    if renderer is not None:
        # Derive unset security config keys using shared helpers
        all_security_keys = _get_all_security_keys()

        unset_security = _get_unset_security_keys(all_security_keys)
        if _config_available:
            existing_config = {}
            for k in all_security_keys:
                try:
                    v = _cfg_get_early(k)
                    if v is not None:
                        existing_config[k] = v
                except Exception as e:
                    print_warning(f"Could not read config key {k}: {e}")
            tts_already_configured = _cfg_get_early("tts_enabled") is not None
            profile_already_configured = _cfg_is_set("profile.default")
        else:
            existing_config = {}
            tts_already_configured = False
            profile_already_configured = False

        # Discover available profiles
        try:
            from spellbook.core.profiles import discover_profiles
            available_profiles = discover_profiles()
        except (ImportError, Exception) as e:
            print_warning(f"Could not discover profiles: {e}")
            available_profiles = []

        wizard_ctx = WizardContext(
            available_platforms=installer.detect_platforms(),
            cli_platforms=args.platforms.split(",") if args.platforms else None,
            unset_security_keys=unset_security,
            existing_config=existing_config,
            security_level=getattr(args, "security_level", None),
            security_wizard=getattr(args, "security_wizard", False),
            tts_disabled=getattr(args, "no_tts", False),
            tts_already_configured=tts_already_configured,
            profile_already_configured=profile_already_configured,
            available_profiles=available_profiles,
            is_upgrade=is_upgrade,
            is_interactive=is_interactive(),
            auto_yes=args.yes,
            no_interactive=args.no_interactive,
            reconfigure=False,
        )

        wizard_results = renderer.render_upfront_wizard(wizard_ctx)
        if wizard_results is None:
            # User cancelled (KeyboardInterrupt/EOFError)
            renderer.render_warning("Installation cancelled.")
            return 1

        # Determine platforms from wizard results
        platforms = wizard_results.platforms or installer.detect_platforms()

        # Apply profile selection immediately (before install)
        if wizard_results.profile_selection is not None and not args.dry_run:
            try:
                from spellbook.core.config import config_set as _cfg_set
                _cfg_set("profile.default", wizard_results.profile_selection)
            except ImportError:
                print("  Warning: could not save profile selection")

        # Resolve security_selections for Installer.run().
        # --security-level flag takes priority over wizard selections.
        # Both renderers now return bare feature IDs (e.g. "crypto"),
        # but we normalize dotted keys as a safety net.
        security_selections = None
        if getattr(args, "security_level", None):
            try:
                from installer.components.security import security_level_to_selections
                security_selections = security_level_to_selections(args.security_level)
            except (ImportError, ValueError) as e:
                print_error(f"Invalid security level: {e}")
                return 1
        elif wizard_results.security_selections is not None:
            security_selections = {}
            for key, value in wizard_results.security_selections.items():
                # Normalize: "security.crypto.enabled" -> "crypto", "crypto" -> "crypto"
                parts = key.split(".")
                bare_id = parts[1] if len(parts) >= 2 else key
                security_selections[bare_id] = value
        elif unset_security and (not getattr(args, "security_wizard", False) or getattr(args, "yes", False)):
            # Security wizard was not requested (or --yes overrides it) and
            # there are unset keys: silently apply recommended defaults.
            security_selections = _get_default_security_selections(unset_security)
    else:
        # No renderer: fallback to old platform selection
        if args.platforms:
            platforms = args.platforms.split(",")
        elif args.yes or args.no_interactive:
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

        # Convert --security-level to security_selections dict (no-renderer path)
        security_selections = None
        if getattr(args, "security_level", None):
            try:
                from installer.components.security import security_level_to_selections
                security_selections = security_level_to_selections(args.security_level)
            except (ImportError, ValueError) as e:
                print_error(f"Invalid security level: {e}")
                return 1
        elif not getattr(args, "security_wizard", False) or getattr(args, "yes", False) or not is_interactive():
            # No --security-wizard, or --yes overrides it, or non-interactive:
            # silently apply recommended defaults for any unset keys.
            try:
                _unset_nr = _get_unset_security_keys(_get_all_security_keys())
                if _unset_nr:
                    security_selections = _get_default_security_selections(_unset_nr)
            except Exception as e:
                print_warning(f"Could not apply security defaults: {e}")

        wizard_results = None  # No wizard in no-renderer path

    # Show directory configuration
    print_directory_config(spellbook_dir, platforms)

    if args.dry_run:
        if renderer is not None:
            renderer.render_warning("DRY RUN - no changes will be made")
        else:
            installer_print_warning("DRY RUN - no changes will be made")

    # Track pending results per section for tree-drawing (plain-text fallback
    # when renderer is unavailable)
    _pending_results: list = []
    _install_timer = InstallTimer()

    def _flush_results():
        """Flush pending results for plain-text fallback mode (no renderer)."""
        if renderer is None:
            for i, r in enumerate(_pending_results):
                print_result(r, is_last=(i == len(_pending_results) - 1))
        _pending_results.clear()

    def _on_progress(event, data):
        """Fallback progress callback used only when renderer is unavailable."""
        if renderer is not None:
            # Renderer handles all display; just collect results for the report
            if event == "result":
                _pending_results.append(data["result"])
            return
        if event == "daemon_start":
            _flush_results()
            print_platform_section("MCP Daemon")
        elif event == "health_start":
            _flush_results()
            print_platform_section("Health Check")
        elif event == "platform_start":
            _flush_results()
            name = data["name"]
            idx = data["index"]
            total = data["total"]
            print_platform_section(name, index=idx, total=total)
        elif event == "platform_skip":
            _flush_results()
            installer_print_info(data["message"])
        elif event == "step":
            # Suppress step messages; results contain all needed info
            pass
        elif event == "result":
            result = data["result"]
            _pending_results.append(result)

    session = installer.run(
        platforms=platforms,
        force=args.force,
        dry_run=args.dry_run,
        on_progress=_on_progress,
        config_dir_overrides=config_dir_overrides if config_dir_overrides else None,
        security_selections=security_selections,
        renderer=renderer,
    )

    # Post-install TTS handling based on wizard results
    if not args.dry_run:
        if wizard_results is not None:
            # Wizard-based flow: use tts_intent from upfront wizard
            if wizard_results.tts_intent is True:
                # User wants TTS; check Wyoming server availability
                if check_tts_available():
                    _set_tts_config(True)
                else:
                    _set_tts_config(True)
                    if renderer is not None:
                        renderer.render_warning(
                            "TTS enabled but Wyoming server not reachable. "
                            "Start a Wyoming TTS server (e.g., wyoming-piper) on localhost:10200"
                        )
                    else:
                        print_warning(
                            "TTS enabled but Wyoming server not reachable. "
                            "Start a Wyoming TTS server (e.g., wyoming-piper) on localhost:10200"
                        )
            elif wizard_results.tts_intent is False:
                _set_tts_config(False)
            # tts_intent is None means skipped; do nothing
        elif not getattr(args, "no_tts", False):
            # No-renderer fallback: use old TTS setup
            if renderer is not None:
                tts_config = renderer.render_tts_wizard()
                if tts_config.get("tts_enabled") is not None:
                    _set_tts_config(tts_config["tts_enabled"])
            else:
                setup_tts(
                    dry_run=args.dry_run,
                    auto_yes=getattr(args, "yes", False),
                    spellbook_dir=spellbook_dir,
                )

    # Flush remaining plain-text results (no-renderer fallback)
    _flush_results()

    if renderer is not None:
        renderer.render_completion(session, elapsed=_install_timer.elapsed())
    else:
        print_report(session, show_details=False, timer=_install_timer)

    # Admin interface config
    admin_enabled = True
    if not args.dry_run:
        try:
            from spellbook.core.config import config_get as _cfg_get, config_set as _cfg_set

            if args.no_admin:
                # Explicit opt-out always wins
                _cfg_set("admin_enabled", False)
                admin_enabled = False
            else:
                existing = _cfg_get("admin_enabled")
                is_upgrade = session.previous_version is not None
                if is_upgrade and existing is False:
                    # User previously disabled admin; respect that on upgrade
                    admin_enabled = False
                else:
                    # Fresh install or upgrade with admin enabled/unset: enable
                    _cfg_set("admin_enabled", True)
                    admin_enabled = True
        except (ImportError, Exception) as e:
            print(f"\nWarning: Could not configure admin interface: {e}")

    if renderer is not None:
        admin_url = "http://localhost:8765/admin" if admin_enabled else ""
        renderer.render_admin_info(admin_url, show_token=admin_enabled)
    else:
        show_admin_info(admin_enabled)

    # Show what's new on upgrade
    if not args.dry_run:
        show_whats_new(spellbook_dir, session.previous_version, session.version)

    # Show post-install instructions
    if not args.dry_run:
        if renderer is not None:
            # Build notes list from installed platforms
            _post_notes: list[str] = []
            for p in session.platforms_installed:
                if p == "gemini":
                    _post_notes.append("Gemini CLI: Restart to load extension. Verify: /extensions list")
                elif p == "opencode":
                    _post_notes.append("OpenCode: Restart to reload skill cache")
                elif p == "codex":
                    _post_notes.append("Codex: AGENTS.md installed. Skills auto-trigger by intent")
                elif p == "claude_code":
                    _post_notes.append("Claude Code: MCP server registered. Verify: /mcp")
            renderer.render_post_install(_post_notes)
        elif is_interactive():
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
    # Ensure stdout/stderr can handle unicode (Windows defaults to cp1252)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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

  # Install to multiple config dirs for a platform
  python3 install.py --claude-config-dir ~/.claude --claude-config-dir ~/.claude-work
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
        "--no-interactive",
        action="store_true",
        help="Skip interactive platform selection",
    )
    parser.add_argument(
        "--no-admin",
        action="store_true",
        help="Disable the web admin interface (enabled by default, persists across upgrades)",
    )
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="Skip bootstrap phase (git clone, uv install). "
             "Used by auto-update after git pull --ff-only. "
             "When combined with --force, skips bootstrap but forces all "
             "installation steps regardless of version.",
    )
    parser.add_argument(
        "--bootstrapped",
        action="store_true",
        help=argparse.SUPPRESS,  # Hidden flag - set after bootstrap phase
    )
    parser.add_argument(
        "--security-level",
        choices=["minimal", "standard", "strict"],
        default=None,
        help="Pre-set security level, skipping the security wizard (minimal|standard|strict)",
    )
    parser.add_argument(
        "--security-wizard",
        action="store_true",
        default=False,
        help="Run interactive security feature selection wizard",
    )
    parser.add_argument(
        "--no-tts",
        action="store_true",
        default=False,
        help="Disable TTS, skipping the TTS setup wizard",
    )
    parser.add_argument(
        "--reconfigure",
        action="store_true",
        default=False,
        help="Re-run the configuration wizard for any unset config keys",
    )

    # Per-platform config dir overrides (repeatable)
    # These are registered dynamically from PLATFORM_CONFIG to stay in sync.
    # Import is deferred because PLATFORM_CONFIG lives in the installer package,
    # which may not be on sys.path until after bootstrap. We use a try/except
    # so the parser can still be built when running from curl-pipe (pre-clone).
    try:
        from installer.config import PLATFORM_CONFIG

        for platform_id, pconfig in PLATFORM_CONFIG.items():
            flag_name = pconfig.get("cli_flag_name")
            if flag_name:
                parser.add_argument(
                    f"--{flag_name}",
                    action="append",
                    type=str,
                    default=None,
                    dest=f"{platform_id}_config_dirs",
                    metavar="DIR",
                    help=(
                        f"Config directory for {pconfig.get('name', platform_id)} "
                        "(repeatable, overrides default and env var). "
                        "Platform must also be selected via --platforms or TUI."
                    ),
                )
    except ImportError:
        # Pre-bootstrap: installer package not yet available.
        # Flags will be available after re-exec from cloned repo.
        pass

    args = parser.parse_args()

    # Auto-enable --yes if not interactive
    if not is_interactive():
        args.yes = True

    # Show a minimal bootstrap status line on initial invocation only.
    # The Rich welcome panel in run_installation() is the real header.
    if not args.bootstrapped:
        print_step("Spellbook: bootstrapping...")

    # Bootstrap phase
    if args.update_only:
        # Skip bootstrap, find spellbook dir directly
        spellbook_dir = find_spellbook_dir()
        if not spellbook_dir:
            print_error("Cannot find spellbook directory. --update-only requires existing install.")
            return 1
        print_success(f"Update-only mode: using {spellbook_dir}")
    else:
        if not args.bootstrapped:
            print_step("Checking prerequisites...")
            print()
        spellbook_dir = bootstrap(args)

    # Installation phase
    return run_installation(spellbook_dir, args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print_warning("Installation cancelled.")
        sys.exit(130)
