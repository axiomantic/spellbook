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
    parser.add_argument(
        "--security-level",
        choices=["minimal", "standard", "strict"],
        default=None,
        help="Pre-set security level, skipping the security wizard (minimal|standard|strict)",
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


def _create_renderer():
    """Create an appropriate renderer for the current environment.

    Returns a ``RichRenderer`` when stdout is a TTY and Rich is available,
    otherwise a ``PlainTextRenderer``.  Returns ``None`` if the renderer
    module cannot be imported at all (should not happen in practice).
    """
    try:
        from installer.renderer import PlainTextRenderer, RichRenderer
        if sys.stdout.isatty():
            return RichRenderer()
        return PlainTextRenderer()
    except ImportError:
        return None


def run(args: argparse.Namespace) -> None:
    """Execute the install command."""
    from installer.core import Installer

    spellbook_dir = _find_spellbook_dir()
    installer = Installer(spellbook_dir)

    renderer = _create_renderer()

    # Show welcome panel
    if renderer is not None:
        renderer.render_welcome(
            version=getattr(installer, "version", "unknown"),
            is_upgrade=False,
        )
        if getattr(args, "dry_run", False):
            renderer.render_warning("DRY RUN - no changes will be made")

    # Convert --security-level to security_selections dict if provided
    security_selections = None
    if getattr(args, "security_level", None):
        try:
            from installer.components.security import security_level_to_selections
            security_selections = security_level_to_selections(args.security_level)
        except (ImportError, ValueError) as e:
            print(f"Error: Invalid security level: {e}", file=sys.stderr)
            sys.exit(1)

    session = installer.run(
        platforms=getattr(args, "platforms", None),
        force=getattr(args, "force", False),
        dry_run=getattr(args, "dry_run", False),
        security_selections=security_selections,
        renderer=renderer,
    )

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
        # Show post-install notes via renderer
        if renderer is not None and not getattr(args, "dry_run", False):
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

        print()
        if session.success:
            print("Installation complete.")
        else:
            print("Installation completed with errors.", file=sys.stderr)
            sys.exit(1)
