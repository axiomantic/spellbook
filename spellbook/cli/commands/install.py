"""``spellbook install`` command.

Delegates to the installer package to set up spellbook for one or more
AI-assistant platforms.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spellbook.cli.formatting import output


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``install`` subcommand."""
    parser = subparsers.add_parser(
        "install",
        help="Install spellbook for AI-assistant platforms",
        description=(
            "Run the spellbook installer.  Auto-detects available platforms "
            "unless --platforms is given."
        ),
    )
    parser.add_argument(
        "--platforms",
        nargs="+",
        default=None,
        help="Platforms to install (e.g. claude_code opencode codex gemini crush)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force reinstall even if version matches",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be done without making changes",
    )
    parser.set_defaults(func=run)


def _find_spellbook_dir() -> Path:
    """Locate the spellbook repository root.

    Checks, in order:
    1. ``SPELLBOOK_DIR`` environment variable
    2. Parent of the installed package location
    """
    import os

    env_dir = os.environ.get("SPELLBOOK_DIR")
    if env_dir:
        return Path(env_dir)

    # Fall back to package location
    try:
        import spellbook

        pkg_dir = Path(spellbook.__file__).parent.parent
        if (pkg_dir / "installer").is_dir():
            return pkg_dir
    except Exception:
        pass

    print(
        "Error: Cannot locate spellbook directory.  Set SPELLBOOK_DIR.",
        file=sys.stderr,
    )
    sys.exit(1)


def _try_import_tui():
    """Try to import TUI components. Returns (available, components) tuple.

    The TUI module uses ``tty``/``termios`` which are Unix-only, and requires
    Rich for rendering.  Returns a dict of callables when available, or an
    empty dict when not.
    """
    try:
        from installer.tui import (
            supports_rich,
            render_welcome_panel,
            render_progress_steps,
            render_dry_run_banner,
            show_post_install_instructions,
        )

        if not supports_rich():
            return False, {}

        from rich.console import Console

        console = Console()
        return True, {
            "console": console,
            "render_welcome_panel": render_welcome_panel,
            "render_progress_steps": render_progress_steps,
            "render_dry_run_banner": render_dry_run_banner,
            "show_post_install_instructions": show_post_install_instructions,
        }
    except Exception:
        return False, {}


def run(args: argparse.Namespace) -> None:
    """Execute the install command."""
    from installer.core import Installer

    spellbook_dir = _find_spellbook_dir()
    installer = Installer(spellbook_dir)

    tui_available, tui = _try_import_tui()

    # Show welcome panel
    if tui_available:
        tui["render_welcome_panel"](tui["console"], version=getattr(installer, "version", None))
        if getattr(args, "dry_run", False):
            tui["render_dry_run_banner"](tui["console"])

    # Accumulated steps for TUI progress rendering
    tui_steps: list = []

    def on_progress(event: str, data: dict) -> None:
        if tui_available:
            _on_progress_tui(event, data)
        else:
            _on_progress_plain(event, data)

    def _on_progress_plain(event: str, data: dict) -> None:
        if event == "step":
            print(f"  {data.get('message', '')}")
        elif event == "platform_start":
            name = data.get("name", "")
            idx = data.get("index", 0)
            total = data.get("total", 0)
            print(f"\n[{idx}/{total}] {name}")
        elif event == "platform_skip":
            print(f"  Skipped: {data.get('message', '')}")
        elif event == "result":
            result = data.get("result")
            if result:
                status = "OK" if result.success else "FAIL"
                print(f"  [{status}] {result.message}")

    def _flush_tui_steps() -> None:
        if tui_steps:
            tui["render_progress_steps"](tui["console"], list(tui_steps))

    def _on_progress_tui(event: str, data: dict) -> None:
        console = tui["console"]
        if event == "platform_start":
            _flush_tui_steps()
            tui_steps.clear()
            name = data.get("name", "")
            idx = data.get("index", 0)
            total = data.get("total", 0)
            console.print()
            console.print(f"[bold cyan][{idx}/{total}] {name}[/bold cyan]")
        elif event == "daemon_start":
            _flush_tui_steps()
            tui_steps.clear()
            console.print()
            console.print("[bold cyan]MCP Daemon[/bold cyan]")
        elif event == "health_start":
            _flush_tui_steps()
            tui_steps.clear()
            console.print()
            console.print("[bold cyan]Health Check[/bold cyan]")
        elif event == "platform_skip":
            tui_steps.append({"name": data.get("message", "Skipped"), "status": "failed"})
        elif event == "step":
            pass  # Suppressed; results carry the info
        elif event == "result":
            result = data.get("result")
            if result:
                status = "done" if result.success else "failed"
                tui_steps.append({"name": result.message, "status": status})

    session = installer.run(
        platforms=getattr(args, "platforms", None),
        force=getattr(args, "force", False),
        dry_run=getattr(args, "dry_run", False),
        on_progress=on_progress,
    )

    # Flush any remaining TUI steps
    if tui_available:
        _flush_tui_steps()

    json_mode = getattr(args, "json", False)
    if json_mode:
        data = {
            "success": session.success,
            "platforms_installed": session.platforms_installed,
            "results": [
                {
                    "component": r.component,
                    "platform": r.platform,
                    "success": r.success,
                    "action": r.action,
                    "message": r.message,
                }
                for r in session.results
            ],
        }
        output(data, json_mode=True)
    else:
        # Show post-install instructions via TUI if available
        if tui_available and not getattr(args, "dry_run", False):
            tui["show_post_install_instructions"](session.platforms_installed)

        print()
        if session.success:
            print("Installation complete.")
        else:
            print("Installation completed with errors.", file=sys.stderr)
            sys.exit(1)
