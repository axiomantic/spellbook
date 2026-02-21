#!/usr/bin/env python3
"""Cross-platform hook wrapper: bash-gate.

On Unix: delegates to bash-gate.sh.
On Windows: native Python implementation.

Claude Code Hook Protocol:
  Receives JSON on stdin: {"tool_name": "Bash", "tool_input": {"command": "..."}}
  Exit 0: allow the tool call
  Exit 2: block the tool call (stdout JSON: {"error": "reason"})
  Any other failure: block (fail-closed)
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).parent


def block(reason: str = "Security check unavailable") -> None:
    """Block with a generic error, never echoing user content."""
    print(json.dumps({"error": reason}))
    sys.exit(2)


def main() -> None:
    if sys.platform != "win32":
        script = HOOK_DIR / "bash-gate.sh"
        os.execv("/bin/bash", ["bash", str(script)] + sys.argv[1:])

    # Windows: native Python implementation
    project_root = os.environ.get("SPELLBOOK_DIR", str(HOOK_DIR.parent))
    check_module = Path(project_root) / "spellbook_mcp" / "security" / "check.py"

    if not check_module.exists():
        block("Security check failed: check module not found")
        return

    stdin_data = sys.stdin.read()
    if not stdin_data:
        block("Security check failed: no input received")
        return

    try:
        result = subprocess.run(
            [sys.executable, "-m", "spellbook_mcp.security.check"],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "PYTHONPATH": project_root},
            cwd=project_root,
        )
    except (OSError, subprocess.TimeoutExpired):
        block("Security check failed: internal error")
        return  # unreachable, but satisfies type checker

    if result.returncode == 0:
        sys.exit(0)
    elif result.returncode == 2:
        if result.stdout.strip():
            print(result.stdout.strip())
        else:
            print(json.dumps({"error": "Security check failed: dangerous pattern detected"}))
        sys.exit(2)
    else:
        block("Security check failed: internal error")
        return


if __name__ == "__main__":
    main()
