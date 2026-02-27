#!/usr/bin/env python3
"""Cross-platform hook wrapper: tts-timer-start.

On Unix: delegates to tts-timer-start.sh.
On Windows: native Python implementation.

Claude Code Hook Protocol (PreToolUse):
  Receives JSON on stdin: {"tool_name": "...", "tool_input": {...}, ...}
  Exit 0: always (timing hook, never blocks)

FAILURE POLICY: FAIL-OPEN
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HOOK_DIR = Path(__file__).parent


def main() -> None:
    if sys.platform != "win32":
        script = HOOK_DIR / "tts-timer-start.sh"
        os.execv("/bin/bash", ["bash", str(script)] + sys.argv[1:])

    # Windows: native Python implementation
    stdin_data = sys.stdin.read()
    if not stdin_data:
        sys.exit(0)

    try:
        data = json.loads(stdin_data)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_use_id = data.get("tool_use_id", "")
    if not tool_use_id:
        sys.exit(0)

    try:
        start_file = Path(tempfile.gettempdir()) / f"claude-tool-start-{tool_use_id}"
        start_file.write_text(str(int(time.time())))
    except OSError:
        pass  # Fail-open

    sys.exit(0)


if __name__ == "__main__":
    main()
