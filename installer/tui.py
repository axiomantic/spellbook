"""
Terminal UI for spellbook installer.

Provides interactive platform selection with checkboxes,
Rich-based welcome panels, feature selection, and progress display.
"""

import sys

try:
    import tty
    import termios
except ImportError:
    # tty/termios are Unix-only; on Windows, interactive terminal
    # functions that depend on them will raise at call time.
    tty = None  # type: ignore[assignment]
    termios = None  # type: ignore[assignment]
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .config import PLATFORM_CONFIG, SUPPORTED_PLATFORMS, platform_exists
from .ui import Colors, color


# ---------------------------------------------------------------------------
# Rich TUI components
# ---------------------------------------------------------------------------


def supports_rich() -> bool:
    """Check if Rich can render in the current terminal.

    Returns False for non-TTY, dumb terminals, or if Rich is not installed.
    """
    try:
        import rich  # noqa: F401
    except ImportError:
        return False

    # Rich is installed; check terminal capability
    term = __import__("os").environ.get("TERM", "")
    if term == "dumb":
        return False

    return True


def render_welcome_panel(
    console: "Any" = None,
    version: Optional[str] = None,
    auto_yes: bool = False,
) -> None:
    """Render the Rich welcome panel with spellbook branding.

    Args:
        console: A ``rich.console.Console`` instance. If None, a default
            Console writing to stdout is created.
        version: Spellbook version string to display. If None, attempts
            to read from the ``.version`` file.
        auto_yes: If True, adjust text for non-interactive mode.
    """
    from rich.panel import Panel
    from rich.text import Text

    if console is None:
        from rich.console import Console
        console = Console()

    if version is None:
        try:
            from pathlib import Path
            vfile = Path(__file__).resolve().parent.parent / ".version"
            if vfile.exists():
                version = vfile.read_text(encoding="utf-8").strip()
        except Exception:
            version = "unknown"

    title_text = Text("Spellbook Installer", style="bold cyan")
    body_parts = [
        f"Version: {version}",
        "",
        "Skills, commands, and MCP tools for AI coding assistants.",
    ]
    body = Text("\n".join(body_parts))
    panel = Panel(body, title=title_text, border_style="cyan", padding=(1, 2))
    console.print(panel)


def render_dry_run_banner(console: "Any") -> None:
    """Render a prominent dry-run mode banner.

    Args:
        console: A ``rich.console.Console`` instance.
    """
    from rich.panel import Panel

    console.print(Panel(
        "[bold yellow]DRY RUN MODE[/bold yellow]\n"
        "No changes will be made. Showing what would happen.",
        border_style="yellow",
        padding=(0, 2),
    ))


def render_progress_steps(
    console: "Any",
    steps: List[Dict[str, str]],
) -> None:
    """Render installation progress steps.

    Args:
        console: A ``rich.console.Console`` instance.
        steps: List of dicts with ``name`` and ``status``
            (``"done"``, ``"pending"``, ``"failed"``).
    """
    from rich.table import Table

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Status", min_width=4, justify="center")
    table.add_column("Step")

    status_icons = {
        "done": "[green]\u2713[/green]",
        "pending": "[dim]\u2022[/dim]",
        "failed": "[red]\u2717[/red]",
        "running": "[cyan]\u25b8[/cyan]",
    }

    for step in steps:
        icon = status_icons.get(step.get("status", "pending"), "[dim]?[/dim]")
        table.add_row(icon, step["name"])

    console.print(table)


# ---------------------------------------------------------------------------
# Live progress display (animated spinners)
# ---------------------------------------------------------------------------


@dataclass
class _StepState:
    """Internal state for a single installation step."""

    name: str
    status: str  # "pending", "running", "done", "failed"


@dataclass
class _SectionState:
    """Internal state for a section (platform or phase)."""

    name: str
    index: int
    total: int
    steps: List["_StepState"]


class LiveProgressDisplay:
    """Animated progress display using Rich Live.

    Shows spinners for active steps, checkmarks for completed, and X marks
    for failures.  Falls back to no-op when Rich is unavailable.
    """

    def __init__(
        self,
        console: "Any" = None,
        dry_run: bool = False,
    ) -> None:
        import time as _time

        self._time = _time
        self._start_time = _time.time()
        self._dry_run = dry_run
        self._sections: List[_SectionState] = []
        self._live: Optional["Any"] = None
        self._console = console
        self._rich_available = supports_rich()

    def start(self) -> None:
        """Enter the Live context and begin rendering."""
        if not self._rich_available:
            return
        from rich.live import Live

        if self._console is None:
            from rich.console import Console
            self._console = Console()

        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=4,
            transient=False,
            get_renderable=self._render,
        )
        self._live.start()

    def stop(self) -> None:
        """Exit the Live context, keeping final output visible."""
        if self._live is not None:
            # Push final renderable so it persists after stop (transient=False)
            self._live.update(self._render())
            self._live.stop()
            self._live = None

    def begin_section(
        self, name: str, index: int = 0, total: int = 0
    ) -> None:
        """Start a new section (platform or phase)."""
        section = _SectionState(
            name=name, index=index, total=total, steps=[]
        )
        self._sections.append(section)
        self._update_display()

    def add_step(self, name: str) -> None:
        """Add a step as 'running' with a spinner."""
        if not self._sections:
            self.begin_section("Installation")
        self._sections[-1].steps.append(_StepState(name=name, status="running"))
        self._update_display()

    def complete_step(self, success: bool = True) -> None:
        """Mark the most recent running step as done or failed."""
        if not self._sections:
            return
        for step in reversed(self._sections[-1].steps):
            if step.status == "running":
                step.status = "done" if success else "failed"
                break
        self._update_display()

    def skip_section(self, message: str) -> None:
        """Add a skipped/failed entry to the current section."""
        if not self._sections:
            self.begin_section("Installation")
        self._sections[-1].steps.append(
            _StepState(name=message, status="failed")
        )
        self._update_display()

    def _update_display(self) -> None:
        """Force an immediate refresh of the Live display."""
        if self._live is None:
            return
        self._live.refresh()

    def _render(self) -> "Any":
        """Build a Rich renderable for the current state."""
        from rich.console import Group
        from rich.spinner import Spinner
        from rich.table import Table
        from rich.text import Text

        renderables: list = []

        for section in self._sections:
            # Section header
            if section.index and section.total:
                header = Text(
                    f"[{section.index}/{section.total}] {section.name}",
                    style="bold cyan",
                )
            else:
                header = Text(section.name, style="bold cyan")
            renderables.append(Text(""))  # blank line
            renderables.append(header)

            # Steps table
            if section.steps:
                table = Table(show_header=False, box=None, padding=(0, 1))
                table.add_column("Status", min_width=4, justify="center")
                table.add_column("Step")

                for step in section.steps:
                    if step.status == "done":
                        icon = Text("\u2713", style="green")
                    elif step.status == "failed":
                        icon = Text("\u2717", style="red")
                    elif step.status == "running":
                        icon = Spinner("dots", style="cyan")
                    else:
                        icon = Text("\u2022", style="dim")
                    table.add_row(icon, step.name)

                renderables.append(table)

        # Elapsed time footer
        elapsed = self._time.time() - self._start_time
        minutes, seconds = divmod(int(elapsed), 60)
        if minutes:
            time_str = f"{minutes}m {seconds}s"
        else:
            time_str = f"{seconds}s"
        renderables.append(Text(""))
        renderables.append(Text(f"Elapsed: {time_str}", style="dim"))

        return Group(*renderables)


def render_completion_summary(
    console: "Any",
    platforms_installed: List[str],
    platforms_failed: Optional[List[str]] = None,
    elapsed_seconds: float = 0.0,
) -> None:
    """Render a styled completion summary panel.

    Args:
        console: A ``rich.console.Console`` instance.
        platforms_installed: List of platform IDs that installed successfully.
        platforms_failed: List of platform IDs that failed (if any).
        elapsed_seconds: Total elapsed time in seconds.
    """
    from rich.panel import Panel

    if platforms_failed is None:
        platforms_failed = []

    has_failures = len(platforms_failed) > 0

    # Build body lines
    lines: List[str] = []

    # Time
    minutes, seconds = divmod(int(elapsed_seconds), 60)
    if minutes:
        time_str = f"{minutes}m {seconds}s"
    else:
        time_str = f"{seconds}s"
    lines.append(f"Total time: {time_str}")
    lines.append("")

    # Installed platforms
    if platforms_installed:
        for p in platforms_installed:
            name = PLATFORM_CONFIG.get(p, {}).get("name", p)
            lines.append(f"  [green]\u2713[/green] {name}")

    # Failed platforms
    if platforms_failed:
        lines.append("")
        for p in platforms_failed:
            name = PLATFORM_CONFIG.get(p, {}).get("name", p)
            lines.append(f"  [red]\u2717[/red] {name}")

    body = "\n".join(lines)

    if has_failures:
        title = "[bold red]Installation Failed[/bold red]"
        border = "red"
    else:
        title = "[bold green]Installation Complete[/bold green]"
        border = "green"

    panel = Panel(body, title=title, border_style=border, padding=(1, 2))
    console.print(panel)


def render_post_install_notes(
    console: "Any",
    platforms: List[str],
) -> None:
    """Render post-install notes as a Rich panel."""
    from rich.panel import Panel

    lines: List[str] = []

    if "gemini" in platforms:
        lines.append("[cyan]Gemini CLI[/cyan]: Restart to load extension. Verify: /extensions list")
    if "opencode" in platforms:
        lines.append("[cyan]OpenCode[/cyan]: Restart to reload skill cache")
    if "codex" in platforms:
        lines.append("[cyan]Codex[/cyan]: AGENTS.md installed. Skills auto-trigger by intent")
    if "claude_code" in platforms:
        lines.append("[cyan]Claude Code[/cyan]: MCP server registered. Verify: /mcp")
    if "forgecode" in platforms:
        lines.append("[cyan]ForgeCode[/cyan]: Restart forge to load the spellbook MCP server")
    if "pi" in platforms:
        lines.append("[cyan]Pi[/cyan]: Restart to reload skills and prompts. Verify: /reload")
    if "goose" in platforms:
        lines.append("[cyan]Goose[/cyan]: Restart to load the spellbook MCP server. Skills in ~/.agents/skills/")

    if lines:
        body = "\n".join(lines)
        panel = Panel(body, title="Next Steps", border_style="dim", padding=(0, 2))
        console.print(panel)


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
    lines.append(color("  (arrows/1-9 to move, space to toggle, a=all, n=none, d=default, enter=confirm)", Colors.BLUE))
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

        num = f"{i + 1}."
        lines.append(f"{prefix}{checkbox} {num:<3} {name:<15} {status}")

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
        elif key in ('a', 'A'):
            # Select all available
            for opt in options:
                if opt.available:
                    opt.selected = True
        elif key in ('n', 'N'):
            # Deselect all
            for opt in options:
                opt.selected = False
        elif key in ('d', 'D'):
            # Reset to auto-detected defaults
            for opt in options:
                opt.selected = opt.available
        elif key.isdigit() and 1 <= int(key) <= len(options):
            idx = int(key) - 1
            if options[idx].available:
                options[idx].selected = not options[idx].selected

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

    if "forgecode" in platforms:
        print(color("  ForgeCode:", Colors.BLUE))
        print("    MCP server registered.")
        print("    Restart forge to load the spellbook MCP server.")
        print()


# ---------------------------------------------------------------------------
# Rule module selection
# ---------------------------------------------------------------------------


@dataclass
class ModuleOption:
    """A rule module option for the checkbox selector.

    PlatformOption is deliberately not reused: it carries ``available``, which
    has no meaning for a module, and omits everything a module needs to explain
    itself.
    """

    id: str
    name: str
    benefit: str
    declining_means: str
    related: List[str]
    size_bytes: int
    default_on: bool
    selected: bool
    previously_declined: bool


def get_module_options(selection: Any) -> List[ModuleOption]:
    """Build selector rows from a resolved ModuleSelection.

    Only preference modules are rendered. The mandatory modules install
    unconditionally, so presenting them as checkboxes would offer a choice that
    does not exist.
    """
    declined = set(selection.declined_ids)
    chosen = set(selection.selected_ids)

    options: List[ModuleOption] = []
    for module in selection.modules:
        if not module.is_preference:
            continue
        options.append(ModuleOption(
            id=module.id,
            name=module.name,
            benefit=module.benefit,
            declining_means=module.declining_means,
            related=list(module.related),
            size_bytes=module.size_bytes,
            default_on=module.default_on,
            selected=module.id in chosen,
            previously_declined=module.id in declined,
        ))
    return options


def _module_row(index: int, opt: ModuleOption, cursor: int) -> str:
    prefix = color("> ", Colors.CYAN) if index == cursor else "  "
    checkbox = color("[x]", Colors.GREEN) if opt.selected else "[ ]"

    if opt.previously_declined:
        name = color(opt.name, Colors.YELLOW)
        note = color(" (previously declined)", Colors.YELLOW)
    elif not opt.default_on:
        name = opt.name
        note = color(" (opt-in)", Colors.BLUE)
    else:
        name = opt.name
        note = ""

    num = f"{index + 1}."
    return f"{prefix}{checkbox} {num:<4}{name:<26} {opt.benefit}{note}"


def render_module_menu(
    options: List[ModuleOption], cursor: int, mandatory_count: int
) -> int:
    """Render the module checkbox menu and return the number of lines drawn."""
    lines = [
        "",
        color("Spellbook rule modules:", Colors.CYAN),
        color(
            "  (arrows/1-9 to move, space to toggle, ? for details, "
            "a=all, n=none, d=defaults, enter=confirm)",
            Colors.BLUE,
        ),
        "",
    ]

    for i, opt in enumerate(options):
        lines.append(_module_row(i, opt, cursor))

    lines.append("")
    lines.append(color(
        f"  {mandatory_count} mandatory modules install unconditionally "
        "and are not listed.",
        Colors.BLUE,
    ))
    lines.append("")

    for line in lines:
        print(line)

    return len(lines)


def render_module_detail(opt: ModuleOption) -> int:
    """Render the detail pane for one module and return lines drawn."""
    default_label = "on" if opt.default_on else "off"
    lines = [
        "",
        color(
            f"  {opt.name}    {opt.size_bytes / 1024:.1f} KB   "
            f"(default: {default_label})",
            Colors.CYAN,
        ),
        "",
        color("  What it does", Colors.BLUE),
        f"    {opt.benefit}",
        "",
        color("  If you decline it", Colors.BLUE),
        f"    {opt.declining_means}",
        "",
        color("  Related spellbook artifacts", Colors.BLUE),
        "    " + (" - ".join(opt.related) if opt.related else "(none)"),
        "",
        color("  press any key to go back", Colors.BLUE),
        "",
    ]
    for line in lines:
        print(line)
    return len(lines)


def termios_available() -> bool:
    """Whether raw-mode terminal control is importable on this interpreter.

    A named function rather than an inline ``termios is not None`` so the
    Windows shape is reachable from a test on a Unix host without reassigning
    a module attribute.
    """
    return termios is not None


def module_select_available() -> bool:
    """Whether this terminal can drive the checkbox selector.

    False on a non-tty, and on Windows, where ``termios`` is absent. Callers use
    it to tell "the user cancelled" apart from "the user was never asked".
    """
    return sys.stdin.isatty() and termios_available()


def interactive_module_select(selection: Any) -> Optional[List[str]]:
    """Show the interactive rule module selection UI.

    Returns the list of selected module ids, or None -- meaning "no answer, so
    record nothing" -- when the user cancelled or when this terminal cannot
    prompt at all.

    Returning the pre-resolved selection on a non-tty was the wrong sentinel:
    callers persist a returned list, so a scripted or Windows install recorded
    True for every default-on module and False for every default-off one,
    permanently marking modules declined that were never offered.
    """
    options = get_module_options(selection)
    if not options:
        return []

    if not module_select_available():
        return None

    mandatory_count = sum(1 for m in selection.modules if m.is_mandatory)
    cursor = 0
    rendered = render_module_menu(options, cursor, mandatory_count)

    while True:
        key = read_key()

        if key == 'UP' or key == 'k':
            cursor = (cursor - 1) % len(options)
        elif key == 'DOWN' or key == 'j':
            cursor = (cursor + 1) % len(options)
        elif key == ' ':
            options[cursor].selected = not options[cursor].selected
        elif key == '?':
            clear_lines(rendered)
            detail_lines = render_module_detail(options[cursor])
            read_key()
            clear_lines(detail_lines)
            rendered = render_module_menu(options, cursor, mandatory_count)
            continue
        elif key == '\r' or key == '\n':
            clear_lines(rendered)
            return [o.id for o in options if o.selected]
        elif key == 'q' or key == '\x03' or key == '\x1b':
            clear_lines(rendered)
            return None
        elif key in ('a', 'A'):
            for opt in options:
                opt.selected = True
        elif key in ('n', 'N'):
            for opt in options:
                opt.selected = False
        elif key in ('d', 'D'):
            for opt in options:
                opt.selected = opt.default_on
        elif key.isdigit() and 1 <= int(key) <= len(options):
            options[int(key) - 1].selected = not options[int(key) - 1].selected

        clear_lines(rendered)
        rendered = render_module_menu(options, cursor, mandatory_count)
