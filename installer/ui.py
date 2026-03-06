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
    get_spellbook_config_dir,
)


class Spinner:
    """
    A simple terminal spinner for showing progress during operations.

    Usage:
        with Spinner("Installing"):
            do_work()
    """

    FRAMES = ["\u280b", "\u2819", "\u2839", "\u2838", "\u283c", "\u2834", "\u2826", "\u2827", "\u2807", "\u280f"]

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

    def update(self, message: str) -> None:
        """Update the spinner message while running."""
        self.message = message

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
    DIM = "\033[2m"
    BOLD = "\033[1m"
    NC = "\033[0m"  # No Color


class InstallTimer:
    """Track elapsed time for the installation."""

    def __init__(self):
        self.start = time.monotonic()

    def elapsed(self):
        return time.monotonic() - self.start

    def formatted(self):
        e = self.elapsed()
        return f"{e:.1f}s"


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
    return color("\u2713", Colors.GREEN)


def cross() -> str:
    return color("\u2717", Colors.RED)


def arrow() -> str:
    return color("\u2192", Colors.BLUE)


def warn() -> str:
    return color("\u26a0", Colors.YELLOW)


def skip() -> str:
    return color("\u2298", Colors.DIM)


# Tree drawing helpers
def tree_mid() -> str:
    """Middle branch of tree."""
    return "  \u251c\u2500 "


def tree_end() -> str:
    """Last branch of tree."""
    return "  \u2514\u2500 "


def print_header(version: str = None) -> None:
    """Print installation header with box-drawing characters."""
    title = f"  Spellbook Installer{f' v{version}' if version else ''}"
    width = max(len(title) + 2, 50)
    print()
    print(f"\u250c{'\u2500' * width}\u2510")
    print(f"\u2502{title:<{width}}\u2502")
    print(f"\u2514{'\u2500' * width}\u2518")
    print()


def print_directory_config(spellbook_dir: Path, platforms: List[str]) -> None:
    """Print directory configuration in compact format."""
    spellbook_config = get_spellbook_config_dir()

    # Shorten home directory to ~
    home = str(Path.home())
    config_display = str(spellbook_config)
    if config_display.startswith(home):
        config_display = "~" + config_display[len(home):]

    print(f"  Source: {spellbook_dir}")
    print(f"  Config: {config_display}")
    print()

    # Platform names
    platform_names = []
    for p in platforms:
        cfg = PLATFORM_CONFIG.get(p, {})
        platform_names.append(cfg.get("name", p))
    print(f"  Platforms: {', '.join(platform_names)}")


def print_platform_section(platform_name: str, index: int = None, total: int = None) -> None:
    """Print platform section header with triangular bullet."""
    counter = f" [{index}/{total}]" if index and total else ""
    print(f"\n\u25b8 {color(platform_name, Colors.BOLD)}{counter}")


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
    print(f"  {color('\u2139', Colors.CYAN)} {message}")


def print_result(result: "InstallResult", is_last: bool = False) -> None:
    """Print a single installation result with tree characters.

    Args:
        result: The installation result to display.
        is_last: If True, use the end-of-tree branch character.
    """
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

    branch = tree_end() if is_last else tree_mid()
    print(f"{branch}{icon} {result.message}")


def print_report(session: "InstallSession", show_details: bool = True, timer: "InstallTimer | None" = None) -> None:
    """Print final installation report.

    Args:
        session: The installation session with results.
        show_details: If True, print per-result details under each platform.
            Set to False when results were already printed inline during install.
        timer: Optional InstallTimer for elapsed time display.
    """
    if show_details:
        # Group results by platform
        by_platform: Dict[str, List["InstallResult"]] = {}
        for result in session.results:
            if result.platform not in by_platform:
                by_platform[result.platform] = []
            by_platform[result.platform].append(result)

        for platform, results in by_platform.items():
            platform_config = PLATFORM_CONFIG.get(platform, {})
            platform_name = platform_config.get("name", platform)
            print_platform_section(platform_name)
            for i, result in enumerate(results):
                print_result(result, is_last=(i == len(results) - 1))

    elapsed = timer.formatted() if timer else None
    if elapsed:
        print(f"\n  Done in {elapsed}")
    else:
        print(f"\n  Done.")
    print()


def print_uninstall_report(session: "InstallSession") -> None:
    """Print uninstallation report."""
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

        print_platform_section(platform_name)
        for i, result in enumerate(results):
            print_result(result, is_last=(i == len(results) - 1))

    print()
