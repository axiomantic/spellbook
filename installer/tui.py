"""
Terminal UI for spellbook installer.

Provides interactive platform selection with checkboxes.
"""

import sys
import tty
import termios
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .config import PLATFORM_CONFIG, SUPPORTED_PLATFORMS, platform_exists
from .ui import Colors, color, supports_color


@dataclass
class PlatformOption:
    """A platform option for the checkbox selector."""

    id: str
    name: str
    available: bool
    selected: bool
    description: str


def get_platform_options() -> List[PlatformOption]:
    """Get list of platform options with availability status."""
    options = []

    for platform_id in SUPPORTED_PLATFORMS:
        config = PLATFORM_CONFIG.get(platform_id, {})
        name = config.get("name", platform_id)

        # Check availability
        if platform_id == "claude_code":
            available = True  # Always available
        else:
            available = platform_exists(platform_id)

        # Description based on availability
        if available:
            desc = "Ready to install"
        else:
            config_dir = config.get("default_config_dir", "")
            desc = f"Not found ({config_dir})"

        options.append(PlatformOption(
            id=platform_id,
            name=name,
            available=available,
            selected=available,  # Default: select if available
            description=desc,
        ))

    return options


def read_key() -> str:
    """Read a single keypress."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)

        # Handle escape sequences (arrow keys)
        if ch == '\x1b':
            ch2 = sys.stdin.read(1)
            if ch2 == '[':
                ch3 = sys.stdin.read(1)
                if ch3 == 'A':
                    return 'UP'
                elif ch3 == 'B':
                    return 'DOWN'

        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def clear_lines(n: int) -> None:
    """Clear n lines above cursor."""
    for _ in range(n):
        sys.stdout.write('\x1b[1A')  # Move up
        sys.stdout.write('\x1b[2K')  # Clear line
    sys.stdout.flush()


def render_checkbox_menu(
    options: List[PlatformOption],
    cursor: int,
    title: str = "Select platforms to install:"
) -> int:
    """
    Render the checkbox menu and return number of lines rendered.
    """
    lines = []

    lines.append("")
    lines.append(color(title, Colors.CYAN))
    lines.append(color("  (use arrows to move, space to toggle, enter to confirm)", Colors.BLUE))
    lines.append("")

    for i, opt in enumerate(options):
        # Cursor indicator
        if i == cursor:
            prefix = color("> ", Colors.CYAN)
        else:
            prefix = "  "

        # Checkbox
        if opt.selected:
            checkbox = color("[x]", Colors.GREEN)
        else:
            checkbox = "[ ]"

        # Platform name and status
        if opt.available:
            name = opt.name
            status = color(f"({opt.description})", Colors.GREEN)
        else:
            name = color(opt.name, Colors.YELLOW)
            status = color(f"({opt.description})", Colors.YELLOW)

        lines.append(f"{prefix}{checkbox} {name} {status}")

    lines.append("")

    for line in lines:
        print(line)

    return len(lines)


def interactive_platform_select() -> Optional[List[str]]:
    """
    Show interactive platform selection UI.

    Returns list of selected platform IDs, or None if cancelled.
    """
    if not sys.stdin.isatty():
        # Non-interactive mode - return all available
        return [p.id for p in get_platform_options() if p.available]

    options = get_platform_options()
    cursor = 0
    rendered_lines = 0

    # Initial render
    rendered_lines = render_checkbox_menu(options, cursor)

    while True:
        key = read_key()

        if key == 'UP' or key == 'k':
            cursor = (cursor - 1) % len(options)
        elif key == 'DOWN' or key == 'j':
            cursor = (cursor + 1) % len(options)
        elif key == ' ':
            # Toggle selection (only if available)
            if options[cursor].available:
                options[cursor].selected = not options[cursor].selected
        elif key == '\r' or key == '\n':
            # Confirm
            clear_lines(rendered_lines)
            selected = [o.id for o in options if o.selected]
            return selected
        elif key == 'q' or key == '\x03' or key == '\x1b':
            # Quit (q, Ctrl+C, Escape)
            clear_lines(rendered_lines)
            return None
        elif key == 'a':
            # Select all available
            for opt in options:
                if opt.available:
                    opt.selected = True
        elif key == 'n':
            # Deselect all
            for opt in options:
                opt.selected = False

        # Re-render
        clear_lines(rendered_lines)
        rendered_lines = render_checkbox_menu(options, cursor)


def confirm_install(platforms: List[str]) -> bool:
    """
    Ask for confirmation before installing.

    Returns True if confirmed, False otherwise.
    """
    if not sys.stdin.isatty():
        return True

    platform_names = []
    for p in platforms:
        config = PLATFORM_CONFIG.get(p, {})
        platform_names.append(config.get("name", p))

    print()
    print(color("Will install to:", Colors.CYAN))
    for name in platform_names:
        print(f"  - {name}")
    print()

    sys.stdout.write(color("Proceed? [Y/n] ", Colors.CYAN))
    sys.stdout.flush()

    response = input().strip().lower()
    return response in ('', 'y', 'yes')


def show_post_install_instructions(platforms: List[str]) -> None:
    """Show platform-specific post-install instructions."""
    print()
    print(color("Post-Installation Notes:", Colors.CYAN))
    print()

    if "gemini" in platforms:
        print(color("  Gemini CLI:", Colors.BLUE))
        print("    The extension has been installed. You may need to restart Gemini CLI.")
        print("    Verify with: gemini (then type /extensions list)")
        print()

    if "opencode" in platforms:
        print(color("  OpenCode:", Colors.BLUE))
        print("    Skills are installed. Restart OpenCode to reload skill cache.")
        print("    Look for: [SkillsPlugin] Discovered X skill(s)")
        print()

    if "codex" in platforms:
        print(color("  Codex:", Colors.BLUE))
        print("    AGENTS.md context file installed.")
        print("    Skills auto-trigger based on your intent (e.g., 'debug this' activates debugging).")
        print()

    if "claude_code" in platforms:
        print(color("  Claude Code:", Colors.BLUE))
        print("    MCP server registered. Skills and commands are ready.")
        print("    Verify with: claude (then /mcp to check server status)")
        print()
