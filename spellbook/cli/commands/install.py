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


def _load_rule_modules(installer):
    """Load the rule modules for a spellbook checkout, or [] if unavailable."""
    from installer.components.rule_modules import get_rules_dir, load_rule_modules

    try:
        return load_rule_modules(get_rules_dir(installer.spellbook_dir))
    except Exception as exc:
        print(f"Warning: could not load rule modules: {exc}")
        return []


def _explicit_rule_config() -> dict:
    """Read only the explicitly-set ``rules.module.*`` keys.

    Absence is a value here -- it means "never offered" -- so the config file
    is read directly rather than through ``config_get``, which would substitute
    each key's built-in default and erase that distinction.
    """
    import json

    from spellbook.core.compat import get_config_dir

    config_path = get_config_dir() / "spellbook.json"
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k.startswith("rules.module.")}


def _select_rule_modules(installer, renderer, args: argparse.Namespace):
    """Prompt for rule module selection, or return None when not asked.

    Returns None -- meaning "not asked, record nothing" -- under ``--dry-run``,
    on a non-tty, under ``--yes``/``--no-interactive``, when the checkout ships
    no modules, and when every preference module is already answered. That is
    the branch that keeps a scripted install from writing an opt-in module to
    True on a user's behalf.
    """
    import sys

    from installer.components.rule_modules import preference_modules, resolve_selection
    from spellbook.core.config import config_is_explicitly_set

    if getattr(args, "dry_run", False):
        return None
    if getattr(args, "yes", False) or getattr(args, "no_interactive", False):
        return None
    if not sys.stdin.isatty():
        return None

    modules = _load_rule_modules(installer)
    if not modules:
        return None

    # Idempotency gate (AGENTS.md "Adding Config Options"): re-prompt only while
    # a key is unset. --reconfigure bypasses it so a declined module can be
    # re-checked, and a newly shipped module re-opens the selector on its own.
    if not getattr(args, "reconfigure", False):
        prefs = preference_modules(modules)
        if prefs and all(config_is_explicitly_set(m.config_key) for m in prefs):
            return None

    selection = resolve_selection(modules, _explicit_rule_config())

    # Through the renderer, never straight to installer.tui. The renderer owns
    # the Windows fallback (a Rich table where termios is absent), so calling
    # the termios selector directly here meant `spellbook install` silently
    # never offered the modules on a machine where `python3 install.py` did.
    if renderer is None:
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
    try:
        return renderer.render_rule_module_select(selection)
    except Exception as exc:
        print(f"Warning: rule module selector unavailable ({exc}); using defaults")
        return None


def _persist_rule_modules(installer, chosen: list[str]) -> None:
    """Record each preference module as kept or declined."""
    from installer.components.rule_modules import preference_modules
    from spellbook.core.config import config_set_many

    modules = _load_rule_modules(installer)
    if not modules:
        return

    selected = set(chosen)
    updates = {m.config_key: (m.id in selected) for m in preference_modules(modules)}
    if not updates:
        return

    try:
        config_set_many(updates)
    except Exception as exc:
        print(f"Warning: could not save rule module selection: {exc}")


def _persist_rule_modules_if_answered(installer, chosen, dry_run: bool) -> None:
    """Record the selection only when the user actually answered it.

    ``None`` is the not-asked sentinel. Persisting it writes an explicit True
    or False for EVERY preference module on the user's behalf, permanently
    marking as declined modules that were never shown -- so the guard lives in
    one named place rather than being re-derived at each call site.
    """
    if chosen is None or dry_run:
        return
    _persist_rule_modules(installer, chosen)


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

        # Offer rule module selection during reconfigure. This is the only path
        # by which a user can re-check a module they previously declined, which
        # is what makes "never re-check automatically" safe to be absolute.
        rule_modules_chosen = _select_rule_modules(installer, renderer, args)
        _persist_rule_modules_if_answered(installer, rule_modules_chosen, is_dry_run)

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

    # Rule module selection. Runs through the same wizard the root installer
    # uses, so both entry points offer the modules and both honor the same
    # tri-state config. A non-tty run skips the prompt and records nothing.
    rule_modules_chosen = _select_rule_modules(installer, renderer, args)

    session = installer.run(
        platforms=getattr(args, "platforms", None),
        force=getattr(args, "force", False),
        dry_run=getattr(args, "dry_run", False),
        renderer=renderer,
        rule_selection=rule_modules_chosen,
    )

    # Config write is last: a failed delivery leaves the prior state standing.
    _persist_rule_modules_if_answered(
        installer, rule_modules_chosen, getattr(args, "dry_run", False)
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


