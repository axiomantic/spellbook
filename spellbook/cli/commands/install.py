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
        help="Platforms to install (e.g. claude_code opencode codex gemini)",
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

    # Handle --reconfigure: run the shared installer wizards for every
    # prompt-registered config key. Each wizard skips its idempotency gate
    # when --reconfigure is active so users can revisit answers.
    if getattr(args, "reconfigure", False):
        is_dry_run = getattr(args, "dry_run", False)
        from spellbook.core.config import config_set

        if not is_dry_run:
            try:
                from installer.wizards import (
                    run_defaults_wizard,
                    run_worker_llm_wizard,
                )
            except ImportError as _exc:
                print(f"Warning: Could not load installer wizards: {_exc}")
            else:
                run_defaults_wizard(args)
                run_worker_llm_wizard(args)

        # Offer profile selection during reconfigure
        if renderer is not None:
            profile_config = renderer.render_profile_wizard(reconfigure=True)
            if "profile.default" in profile_config and not is_dry_run:
                config_set("profile.default", profile_config["profile.default"])
        return

    # Show welcome panel
    if renderer is not None:
        renderer.render_welcome(
            version=getattr(installer, "version", "unknown"),
            is_upgrade=False,
        )
        if getattr(args, "dry_run", False):
            renderer.render_warning("DRY RUN - no changes will be made")

    session = installer.run(
        platforms=getattr(args, "platforms", None),
        force=getattr(args, "force", False),
        dry_run=getattr(args, "dry_run", False),
        renderer=renderer,
    )

    # Defaults wizard for previously never-prompted keys (notify_*,
    # auto_update, session_mode). Idempotent: each key is skipped when
    # already explicitly set unless --reconfigure is active.
    if not getattr(args, "dry_run", False):
        from installer.wizards import run_defaults_wizard
        run_defaults_wizard(args)

    # Worker LLM endpoint wizard (optional; default OFF so existing users
    # see zero behavior change). Skipped under --dry-run and on non-tty stdin
    # (CI, piped installs) so the installer never blocks.
    if not getattr(args, "dry_run", False):
        from installer.wizards import run_worker_llm_wizard
        run_worker_llm_wizard(args)

    # Memory system setup (QMD + Serena)
    if not getattr(args, "dry_run", False):
        try:
            from installer.components.memory import (
                is_qmd_installed,
                is_serena_installed,
                setup_memory_system,
            )
        except ImportError:
            setup_memory_system = None  # type: ignore

        if setup_memory_system is not None:
            qmd_have = is_qmd_installed()
            serena_have = is_serena_installed()
            if not (qmd_have and serena_have) and sys.stdin.isatty():
                print()
                print("Memory system: requires QMD + Serena (~200MB, ~30s install)")
                resp = input("Enable memory system? [y/N]: ").strip().lower()
                enable = resp in ("y", "yes")
                if enable:
                    result = setup_memory_system(True)
                    if result["qmd"] and result["serena"]:
                        print("  Memory system: ready")
                    else:
                        missing = []
                        if not result["qmd"]:
                            missing.append("QMD")
                        if not result["serena"]:
                            missing.append("Serena")
                        print(
                            "  Warning: could not install: "
                            + ", ".join(missing)
                            + " (continuing without memory system)"
                        )

    # Profile selection
    if not getattr(args, "dry_run", False):
        if renderer is not None:
            profile_config = renderer.render_profile_wizard()
            if "profile.default" in profile_config:
                try:
                    from spellbook.core.config import config_set as _cfg_set
                    _cfg_set("profile.default", profile_config["profile.default"])
                except ImportError:
                    print("  Warning: could not save profile selection (spellbook.core.config not available)")

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
                elif p == "forgecode":
                    _post_notes.append("ForgeCode: Restart forge to load the spellbook MCP server")
            renderer.render_post_install(_post_notes)

        print()
        if session.success:
            print("Installation complete.")
        else:
            print("Installation completed with errors.", file=sys.stderr)
            sys.exit(1)


# ---------------------------------------------------------------------------
# Worker LLM wizard -- thin shim preserved for backward compatibility with
# tests and external callers. Logic lives in installer.wizards.worker_llm
# so both this entry path and the root install.py share a single prompt
# implementation.
# ---------------------------------------------------------------------------


def _run_worker_llm_wizard() -> None:
    """Backward-compat wrapper delegating to the shared wizard."""
    from installer.wizards import run_worker_llm_wizard
    run_worker_llm_wizard(None)


