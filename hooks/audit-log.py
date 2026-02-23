#!/usr/bin/env python3
"""Cross-platform hook wrapper: audit-log.

On Unix: delegates to audit-log.sh.
On Windows: native Python implementation.

Claude Code Hook Protocol (PostToolUse):
  Receives JSON on stdin: {"tool_name": "...", "tool_input": {...}}
  Exit 0: always (this hook NEVER blocks tool execution)

FAILURE POLICY: FAIL-OPEN
  Logging failures must NEVER prevent tool execution. All error paths
  exit 0.
"""
import os
import subprocess
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).parent


def main() -> None:
    if sys.platform != "win32":
        script = HOOK_DIR / "audit-log.sh"
        os.execv("/bin/bash", ["bash", str(script)] + sys.argv[1:])

    # Windows: native Python implementation
    project_root = os.environ.get("SPELLBOOK_DIR", str(HOOK_DIR.parent))

    stdin_data = sys.stdin.read()
    if not stdin_data:
        sys.exit(0)  # Fail-open

    try:
        subprocess.run(
            [sys.executable, "-m", "spellbook_mcp.security.check", "--mode", "audit"],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "PYTHONPATH": project_root},
            cwd=project_root,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass  # Fail-open: never block tool execution

    sys.exit(0)


if __name__ == "__main__":
    main()
