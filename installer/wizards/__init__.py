"""Shared installer wizards.

Each module exports a single ``run_<name>_wizard(args)`` function invoked
from both the root ``install.py`` entry path and
``spellbook.cli.commands.install``. Keeping the prompt logic in one place
guarantees parity between the two entry points so every user-facing config
option is offered through both.
"""

from installer.wizards.worker_llm import run_worker_llm_wizard

__all__ = ["run_worker_llm_wizard"]
