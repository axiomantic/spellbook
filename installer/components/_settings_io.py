"""Shared settings.json reader for installer components.

default_mode.py and permissions.py both need to load Claude Code settings
into a dict, treating "missing file" and "empty file" as "no settings".
Keep one canonical implementation here so future edge-case handling
(encoding fallbacks, schema validation) doesn't drift between modules.
"""

import json
from pathlib import Path


def read_settings(settings_path: Path) -> dict:
    """Read settings.json; return {} when the file is absent or empty.

    Raises ``json.JSONDecodeError`` on malformed JSON and ``OSError``
    on read failures; callers handle those to emit failed HookResults.
    """
    if not settings_path.exists():
        return {}
    text = settings_path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    return json.loads(text)
