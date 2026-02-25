"""
Terminal output formatting for spellbook installer.
"""

import itertools
import os
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from .core import InstallResult, InstallSession

from .config import (
    PLATFORM_CONFIG,
    SPELLBOOK_DEFAULT_CONFIG_DIR,
    get_platform_config_dir,
    get_spellbook_config_dir,
)


class Spinner:
    """
    A simple terminal spinner for showing progress during operations.

    Usage:
        with Spinner("Installing"):
            do_work()
    """

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Working", delay: float = 0.1):
        self.message = message
        self.delay = delay
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def _spin(self) -> None:
        """Spinner thread loop."""
        frames = itertools.cycle(self.FRAMES)
        while not self._stop_event.is_set():
            frame = next(frames)
            sys.stdout.write(f"\r{frame} {self.message}...")
            sys.stdout.flush()
            time.sleep(self.delay)

    def start(self) -> None:
        """Start the spinner."""
        if not sys.stdout.isatty():
            # Non-interactive, just print message
            print(f"{self.message}...")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self, success: bool = True) -> None:
        """Stop the spinner and show result."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        if sys.stdout.isatty():
            # Clear the spinner line
            sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
            sys.stdout.flush()

    def __enter__(self) -> "Spinner":
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()


class Colors:
    """ANSI color codes."""

    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    BOLD = "\033[1m"
    NC = "\033[0m"  # No Color


# Check if output supports colors
def supports_color() -> bool:
    """Check if terminal supports colors."""
    if not hasattr(sys.stdout, "isatty"):
        return False
    if not sys.stdout.isatty():
        return False
    return True


# Conditionally apply colors
def color(text: str, color_code: str) -> str:
    """Apply color if supported."""
    if supports_color():
        return f"{color_code}{text}{Colors.NC}"
    return text


# Status symbols
def check() -> str:
    return color("[ok]", Colors.GREEN)


def cross() -> str:
    return color("[fail]", Colors.RED)


def arrow() -> str:
    return color("->", Colors.BLUE)


def warn() -> str:
    return color("[!]", Colors.YELLOW)


def skip() -> str:
    return color("[skip]", Colors.CYAN)


def print_header(version: str) -> None:
    """Print installation header."""
    print()
    line = "=" * 60
    print(color(line, Colors.CYAN))
    print(color(f"  Spellbook Installer v{version}", Colors.CYAN))
    print(color(line, Colors.CYAN))
    print()


def print_directory_config(spellbook_dir: Path, platforms: List[str]) -> None:
    """Print directory configuration showing where files will be installed."""
    print(color("Directory Configuration:", Colors.CYAN))
    print()

    # Spellbook source
    print(f"  {color('Source:', Colors.BOLD)}")
    print(f"    SPELLBOOK_DIR = {spellbook_dir}")
    print()

    # Spellbook output directory
    spellbook_config = get_spellbook_config_dir()
    is_custom_output = os.environ.get('SPELLBOOK_CONFIG_DIR')
    print(f"  {color('Output Directory:', Colors.BOLD)}")
    print(f"    SPELLBOOK_CONFIG_DIR = {spellbook_config}")
    if is_custom_output:
        print(f"    {color('(from $SPELLBOOK_CONFIG_DIR)', Colors.YELLOW)}")
    else:
        print(f"    {color('(default)', Colors.CYAN)}")
    print()

    # Platform targets
    print(f"  {color('Platform Targets:', Colors.BOLD)}")
    for platform in platforms:
        config = PLATFORM_CONFIG.get(platform, {})
        platform_name = config.get("name", platform)
        config_dir = get_platform_config_dir(platform)

        # Check if using custom env var
        env_var = config.get("config_dir_env")
        is_custom = env_var and os.environ.get(env_var)

        print(f"    {platform_name}:")
        print(f"      {config_dir}")
        if is_custom:
            print(f"      {color(f'(from ${env_var})', Colors.YELLOW)}")

    print()
    print(color("-" * 60, Colors.CYAN))
    print()


def print_platform_section(platform_name: str) -> None:
    """Print platform section header."""
    print(f"\n{color(f'>>> {platform_name}', Colors.BLUE)}")


def print_step(message: str) -> None:
    """Print a step message."""
    print(f"  {arrow()} {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"  {check()} {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"  {cross()} {message}", file=sys.stderr)


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"  {warn()} {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"  {color('[i]', Colors.CYAN)} {message}")


def print_result(result: "InstallResult") -> None:
    """Print a single installation result."""
    if result.action == "installed":
        icon = check()
    elif result.action == "upgraded":
        icon = check()
    elif result.action == "created":
        icon = check()
    elif result.action == "skipped":
        icon = skip()
    elif result.action == "failed":
        icon = cross()
    elif result.action == "unchanged":
        icon = skip()
    else:
        icon = arrow()

    print(f"    {icon} {result.message}")


def print_report(session: "InstallSession") -> None:
    """Print final installation report."""
    print()
    line = "=" * 60
    print(color(line, Colors.CYAN))
    print(color("  Installation Summary", Colors.CYAN))
    print(color(line, Colors.CYAN))
    print()

    # Group results by platform
    by_platform: Dict[str, List["InstallResult"]] = {}
    for result in session.results:
        if result.platform not in by_platform:
            by_platform[result.platform] = []
        by_platform[result.platform].append(result)

    # Track platforms for quick start
    ready_platforms = []

    # Print per-platform summary
    for platform, results in by_platform.items():
        platform_config = PLATFORM_CONFIG.get(platform, {})
        platform_name = platform_config.get("name", platform)
        success_count = sum(1 for r in results if r.success)
        total_count = len(results)

        if success_count == total_count:
            status = color("Ready", Colors.GREEN)
            ready_platforms.append(platform)
        elif success_count > 0:
            status = color("Partial", Colors.YELLOW)
            ready_platforms.append(platform)
        else:
            status = color("Failed", Colors.RED)

        print(f"  {platform_name}: {status}")

        # Show key details
        for result in results:
            print_result(result)

        print()

    # Print quick start instructions
    print(color("Quick Start:", Colors.CYAN))
    print()

    if "claude_code" in ready_platforms:
        print("  Claude Code:")
        print("    $ claude")
        print()

    if "gemini" in ready_platforms:
        print("  Gemini CLI:")
        print("    $ gemini")
        print()

    if "opencode" in ready_platforms:
        print("  OpenCode:")
        print("    Skills available in ~/.config/opencode/skills/")
        print()

    if "codex" in ready_platforms:
        print("  Codex:")
        print("    Skills auto-trigger based on your intent.")
        print()

    # Print source location
    print(f"{color('Spellbook location:', Colors.CYAN)} {session.spellbook_dir}")
    print(f"{color('Version:', Colors.CYAN)} {session.version}")

    if session.previous_version and session.previous_version != session.version:
        print(f"{color('Upgraded from:', Colors.CYAN)} {session.previous_version}")

    print()


def print_uninstall_report(session: "InstallSession") -> None:
    """Print uninstallation report."""
    print()
    line = "=" * 60
    print(color(line, Colors.CYAN))
    print(color("  Uninstallation Summary", Colors.CYAN))
    print(color(line, Colors.CYAN))
    print()

    # Group results by platform
    by_platform: Dict[str, List["InstallResult"]] = {}
    for result in session.results:
        if result.platform not in by_platform:
            by_platform[result.platform] = []
        by_platform[result.platform].append(result)

    # Print per-platform summary
    for platform, results in by_platform.items():
        platform_config = PLATFORM_CONFIG.get(platform, {})
        platform_name = platform_config.get("name", platform)
        removed_count = sum(1 for r in results if r.action in ("removed", "deleted"))

        print(f"  {platform_name}:")
        for result in results:
            print_result(result)
        print()

    print()
