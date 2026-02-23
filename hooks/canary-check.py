#!/usr/bin/env python3
"""Cross-platform hook wrapper: canary-check.

On Unix: delegates to canary-check.sh.
On Windows: native Python implementation.

Claude Code Hook Protocol (PostToolUse):
  Receives JSON on stdin: {"tool_name": "...", "tool_input": {...}, "tool_output": "..."}
  Exit 0: always (this hook NEVER blocks tool execution)

FAILURE POLICY: FAIL-OPEN
  Canary check failures must NEVER prevent tool execution. All error paths
  exit 0.
"""
import os
import subprocess
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).parent


def main() -> None:
    if sys.platform != "win32":
        script = HOOK_DIR / "canary-check.sh"
        os.execv("/bin/bash", ["bash", str(script)] + sys.argv[1:])

    # Windows: native Python implementation
    project_root = os.environ.get("SPELLBOOK_DIR", str(HOOK_DIR.parent))

    stdin_data = sys.stdin.read()
    if not stdin_data:
        sys.exit(0)  # Fail-open

    try:
        # stderr passes through so canary warnings reach the user
        subprocess.run(
            [sys.executable, "-m", "spellbook_mcp.security.check", "--mode", "canary"],
            input=stdin_data,
            capture_output=False,
            text=True,
            timeout=10,
            env={**os.environ, "PYTHONPATH": project_root},
            cwd=project_root,
            stdout=subprocess.PIPE,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass  # Fail-open: never block tool execution

    sys.exit(0)


if __name__ == "__main__":
    main()
