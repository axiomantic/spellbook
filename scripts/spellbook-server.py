#!/usr/bin/env python3
"""Thin wrapper - delegates to spellbook.daemon.manager."""
import warnings

warnings.warn(
    "scripts/spellbook-server.py is deprecated. Use 'spellbook server <command>' instead.",
    DeprecationWarning,
    stacklevel=1,
)
from spellbook.daemon.manager import main

if __name__ == "__main__":
    main()
