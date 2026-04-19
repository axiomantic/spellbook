"""Shared worker-LLM installer wizard.

Invoked from both the root ``install.py`` entry path and
``spellbook.cli.commands.install`` so every install flow offers the same
prompts. Writes config via :func:`spellbook.core.config.config_set`; one
key per call so a partial failure never leaves the config half-written.

The wizard is a noop when stdin is not a tty (CI / piped installs) and
when ``args.dry_run`` is truthy.
"""

from __future__ import annotations

import sys as _sys
from typing import Any, Optional


def run_worker_llm_wizard(args: Optional[Any] = None) -> None:
    """Prompt the user to configure an OpenAI-compatible worker LLM endpoint.

    Args:
        args: Optional argparse ``Namespace``. Checked for ``dry_run``
            (skip if True) and ``reconfigure`` (bypass idempotency gate
            if True). ``None`` is treated as ``dry_run=False`` and
            ``reconfigure=False``.
    """
    if not _sys.stdin.isatty():
        return

    if getattr(args, "dry_run", False):
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

    # 5) Four feature flags -- always ask for all four; write the explicit
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
