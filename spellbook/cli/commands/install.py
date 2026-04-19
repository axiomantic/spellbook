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

    # Handle --reconfigure: run config wizard for unset keys only
    if getattr(args, "reconfigure", False):
        is_dry_run = getattr(args, "dry_run", False)
        from spellbook.core.config import get_unset_config_keys, config_set

        unset_keys = get_unset_config_keys()
        if unset_keys and renderer is not None:
            selections = renderer.render_config_wizard(unset_keys, {}, is_upgrade=False)
            if not is_dry_run:
                for key, value in selections.items():
                    config_set(key, value)

        # Offer profile selection during reconfigure
        if renderer is not None:
            profile_config = renderer.render_profile_wizard(reconfigure=True)
            if "profile.default" in profile_config and not is_dry_run:
                config_set("profile.default", profile_config["profile.default"])

        if not unset_keys:
            print("All config keys are already set.")
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

    # TTS setup runs after the install loop completes
    if not getattr(args, "dry_run", False) and not getattr(args, "no_tts", False):
        if renderer is not None:
            tts_config = renderer.render_tts_wizard()
            if tts_config.get("tts_enabled") is not None:
                try:
                    from spellbook.core.config import config_set as _cfg_set
                    _cfg_set("tts_enabled", tts_config["tts_enabled"])
                except ImportError:
                    pass
            if tts_config.get("tts_install"):
                try:
                    from installer.components.mcp import install_tts_to_daemon_venv
                    success, _msg = install_tts_to_daemon_venv(spellbook_dir)
                    if success:
                        from spellbook.core.config import config_set as _cfg_set
                        _cfg_set("tts_enabled", True)
                except (ImportError, Exception):
                    pass

    # Worker LLM endpoint wizard (optional; default OFF so existing users
    # see zero behavior change). Skipped under --dry-run and on non-tty stdin
    # (CI, piped installs) so the installer never blocks.
    if not getattr(args, "dry_run", False):
        _run_worker_llm_wizard()

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

    # Profile selection runs after TTS
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
            renderer.render_post_install(_post_notes)

        print()
        if session.success:
            print("Installation complete.")
        else:
            print("Installation completed with errors.", file=sys.stderr)
            sys.exit(1)


# ---------------------------------------------------------------------------
# Worker LLM wizard
# ---------------------------------------------------------------------------


def _run_worker_llm_wizard() -> None:
    """Prompt the user to configure an OpenAI-compatible worker LLM endpoint.

    Design decision: this wizard uses plain ``input()`` rather than a renderer
    method (unlike the TTS wizard) to keep the surface area small. The
    precedent is the memory-system block at :func:`run`: both the memory-
    system and worker-LLM wizards are opt-in, default-off, low-traffic
    setup flows that do not justify dual RichRenderer/PlainTextRenderer
    implementations.

    The function is a noop when stdin is not a tty so CI / piped installers
    do not block. Writes config via :func:`spellbook.core.config.config_set`;
    one key per ``config_set`` call so a partial failure does not leave the
    config in a half-written state.

    See design doc §9.
    """
    import sys as _sys

    if not _sys.stdin.isatty():
        return

    print()
    resp = input(
        "Do you have a local or remote OpenAI-compatible LLM endpoint you'd "
        "like spellbook to use for background tasks? [y/N]: "
    ).strip().lower()
    if resp not in ("y", "yes"):
        return

    # 1) Probe for running local endpoints.
    try:
        import asyncio

        from spellbook.worker_llm.probe import probe_all

        detected = asyncio.run(probe_all(timeout_total_s=2.0))
    except Exception as e:  # noqa: BLE001
        print(f"  (probe failed: {type(e).__name__}: {e}; continuing)")
        detected = []

    # 2) Pick or manually enter the endpoint.
    chosen_url: str = ""
    chosen_models: list[str] = []
    if detected:
        print()
        print("Detected local endpoints:")
        for i, ep in enumerate(detected, start=1):
            models_count = len(ep.models)
            print(
                f"  {i}. {ep.base_url} ({ep.label}, {models_count} model(s))"
            )
        print(f"  {len(detected) + 1}. Enter URL manually")
        while True:
            raw = input(
                f"Select endpoint [1-{len(detected) + 1}]: "
            ).strip()
            try:
                idx = int(raw)
            except ValueError:
                print("  Please enter a number.")
                continue
            if 1 <= idx <= len(detected):
                chosen_url = detected[idx - 1].base_url
                chosen_models = list(detected[idx - 1].models)
                break
            if idx == len(detected) + 1:
                chosen_url = input("Base URL: ").strip()
                break
            print("  Out of range.")
    else:
        chosen_url = input(
            "Base URL (e.g. http://localhost:11434/v1): "
        ).strip()

    if not chosen_url:
        print("  No URL provided; wizard aborted.")
        return

    # 3) Pick or enter a model. Default to qwen2.5-coder:7b per design §9.
    default_model = (
        chosen_models[0] if chosen_models else "qwen2.5-coder:7b"
    )
    if chosen_models:
        print()
        print("Available models:")
        for i, m in enumerate(chosen_models, start=1):
            print(f"  {i}. {m}")
        print(f"  {len(chosen_models) + 1}. Enter manually")
        while True:
            raw = input(
                f"Select model [1-{len(chosen_models) + 1}, default 1]: "
            ).strip()
            if not raw:
                chosen_model = chosen_models[0]
                break
            try:
                idx = int(raw)
            except ValueError:
                print("  Please enter a number.")
                continue
            if 1 <= idx <= len(chosen_models):
                chosen_model = chosen_models[idx - 1]
                break
            if idx == len(chosen_models) + 1:
                chosen_model = input("Model id: ").strip() or default_model
                break
            print("  Out of range.")
    else:
        chosen_model = (
            input(f"Model id [{default_model}]: ").strip() or default_model
        )

    # 4) Optional API key (blank allowed for local endpoints).
    chosen_key = input("API key (blank for local endpoints): ").strip()

    # 5) Four feature flags — always ask for all four; write the explicit
    # value (including False) so the keys are persisted and there is no
    # ambiguity between "user said no" and "key absent".
    features: dict[str, bool] = {}
    feature_prompts = [
        (
            "transcript_harvest",
            "Enable worker-LLM semantic Stop-hook memory harvest? "
            "(REPLACE mode by default; worker supersedes regex harvester) [y/N]: ",
        ),
        (
            "tool_safety",
            "Enable worker-LLM PreToolUse safety sniff (OK/WARN/BLOCK)? "
            "(Fails OPEN on 1.5s timeout; BLOCK verdicts bypassable within 30s) [y/N]: ",
        ),
        (
            "memory_rerank",
            "Enable worker-LLM reranking of memory_recall candidates? "
            "(Adds one worker call per memory_recall invocation) [y/N]: ",
        ),
        (
            "read_claude_memory",
            "Also include Claude Code's MEMORY.md files in memory_recall? "
            "(Independent of worker LLM; safe to enable without an endpoint) [y/N]: ",
        ),
    ]
    for name, prompt in feature_prompts:
        ans = input(prompt).strip().lower()
        features[name] = ans in ("y", "yes")

    # 6) Write config. One key per config_set call so a partial failure
    # does not leave the config in a half-written state.
    try:
        from spellbook.core.config import config_set
    except ImportError:
        print("  Error: could not import config_set; aborted.")
        return

    try:
        config_set("worker_llm_base_url", chosen_url)
        config_set("worker_llm_model", chosen_model)
        if chosen_key:
            config_set("worker_llm_api_key", chosen_key)
        config_set(
            "worker_llm_feature_transcript_harvest",
            bool(features["transcript_harvest"]),
        )
        config_set(
            "worker_llm_feature_tool_safety", bool(features["tool_safety"])
        )
        config_set(
            "worker_llm_feature_memory_rerank",
            bool(features["memory_rerank"]),
        )
        config_set(
            "worker_llm_read_claude_memory",
            bool(features["read_claude_memory"]),
        )
    except Exception as e:  # noqa: BLE001
        print(f"  Error writing config: {type(e).__name__}: {e}")
        return

    print()
    print(
        f"  Worker LLM configured: {chosen_url} ({chosen_model}). "
        "Run `spellbook worker-llm doctor` to verify."
    )

    # 6.5) Drop a breadcrumb README in the override directory so users who
    # want to customize a task prompt can discover the convention without
    # reading source. Gated on ``worker_llm_allow_prompt_overrides`` so it
    # only appears when overrides are actually respected at load time.
    _write_worker_prompt_override_readme()

    # 7) Offer to run doctor inline.
    run_doctor = input("Run doctor now? [y/N]: ").strip().lower()
    if run_doctor in ("y", "yes"):
        try:
            import argparse as _ap

            from spellbook.cli.commands.worker_llm import _run_doctor

            doctor_args = _ap.Namespace(
                json=False, bench=None, runs=10, roundtable_sample=None
            )
            try:
                _run_doctor(doctor_args)
            except SystemExit:
                pass
        except Exception as e:  # noqa: BLE001
            print(f"  (doctor failed to run: {type(e).__name__}: {e})")


# ---------------------------------------------------------------------------
# Worker prompt override breadcrumb
# ---------------------------------------------------------------------------


_WORKER_PROMPT_OVERRIDE_README = """\
# Worker LLM prompt overrides

This directory lets you override the default system prompts that ship with
spellbook for worker-LLM background tasks. If a matching file exists here,
spellbook loads it instead of the built-in default.

## Supported tasks

Drop a file named `<task>.md` into this directory to override that task:

- `transcript_harvest.md` - Stop-hook memory extraction from assistant output.
- `memory_rerank.md`      - Reranks `memory_recall` candidates by relevance.
- `roundtable_voice.md`   - Drives tarot-mode roundtable archetype voices.
- `tool_safety.md`        - PreToolUse OK/WARN/BLOCK safety sniff.

## File format

Each file is plain markdown and replaces the task's **system prompt**
verbatim. There are no `{placeholder}` substitutions: the user-side payload
(tool input, transcript text, candidate list, dialogue) is injected by the
task at call time on its own turn, not interpolated into this file. See
`spellbook/worker_llm/default_prompts/<task>.md` for the current built-in
version of each prompt to use as a starting point.

## Verifying an override is live

After dropping a file, run `spellbook worker-llm doctor` - it reports which
prompts are currently overridden. The worker also writes a one-line
`[worker-llm] using override prompt for <task>` notice to stderr the first
time it loads your version in a session.

## Disabling overrides

Set `worker_llm_allow_prompt_overrides` to `false` via `spellbook config set`
to make the worker ignore this directory entirely and always use defaults.
"""


def _write_worker_prompt_override_readme() -> None:
    """Create a breadcrumb README in the prompt-override directory.

    Noop when ``worker_llm_allow_prompt_overrides`` resolves to False (the
    worker will not respect overrides anyway, so the breadcrumb would be
    misleading). Never overwrites an existing README - prints an
    "already exists" notice instead so a user's local edits are preserved
    across reinstalls.

    Errors are caught and logged to stdout: the wizard has already written
    the config successfully at this point, and a failed breadcrumb MUST NOT
    abort the install flow.
    """
    try:
        from spellbook.worker_llm.config import get_worker_config
        from spellbook.worker_llm.prompts import OVERRIDE_PROMPT_DIR
    except ImportError as e:
        print(f"  (override README skipped: {type(e).__name__}: {e})")
        return

    try:
        cfg = get_worker_config()
    except Exception as e:  # noqa: BLE001
        print(f"  (override README skipped: {type(e).__name__}: {e})")
        return

    if not cfg.allow_prompt_overrides:
        # User (or admin) has disabled overrides; don't drop a breadcrumb
        # that points at a path the worker won't read.
        return

    try:
        OVERRIDE_PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"  (override README skipped: could not create {OVERRIDE_PROMPT_DIR}: {e})")
        return

    readme_path = OVERRIDE_PROMPT_DIR / "README.md"
    if readme_path.exists():
        print(f"  Worker prompt override README already exists at {readme_path}; leaving it alone.")
        return

    try:
        readme_path.write_text(_WORKER_PROMPT_OVERRIDE_README, encoding="utf-8")
    except OSError as e:
        print(f"  (override README skipped: could not write {readme_path}: {e})")
        return

    print(f"  Worker prompt override README written to {readme_path}.")
