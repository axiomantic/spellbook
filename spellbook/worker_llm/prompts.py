"""Prompt loader with filesystem-override convention.

Resolution order:
  1. Override at ``~/.local/spellbook/worker_prompts/<task>.md`` (only if
     ``worker_llm_allow_prompt_overrides`` is True).
  2. Package default at ``spellbook/worker_llm/default_prompts/<task>.md``.

When an override is loaded, an ``override_loaded`` event is published via
``publish_override_loaded`` and a one-line notice is written to stderr so the
fact is visible in both the admin UI and the local terminal.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from spellbook.worker_llm.config import get_worker_config
from spellbook.worker_llm.events import publish_override_loaded

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_DIR = Path(__file__).parent / "default_prompts"
OVERRIDE_PROMPT_DIR = Path.home() / ".local" / "spellbook" / "worker_prompts"

_KNOWN_TASKS = frozenset(
    {"transcript_harvest", "memory_rerank", "roundtable_voice", "tool_safety"}
)


def load(task_name: str) -> tuple[str, bool]:
    """Return ``(prompt_text, override_loaded)`` for the named task.

    Raises:
        ValueError: ``task_name`` not in the known task set.
        FileNotFoundError: Default file missing from the package (packaging bug).
    """
    if task_name not in _KNOWN_TASKS:
        raise ValueError(f"Unknown worker-llm task: {task_name}")

    cfg = get_worker_config()
    override_path = OVERRIDE_PROMPT_DIR / f"{task_name}.md"
    if cfg.allow_prompt_overrides and override_path.exists():
        try:
            text = override_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("override read failed for %s: %s", task_name, e)
        else:
            publish_override_loaded(task=task_name, path=str(override_path))
            print(
                f"[worker-llm] using override prompt for {task_name}",
                file=sys.stderr,
            )
            return text, True

    default_path = DEFAULT_PROMPT_DIR / f"{task_name}.md"
    return default_path.read_text(encoding="utf-8"), False
