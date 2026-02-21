#!/usr/bin/env python3
"""Cross-platform hook wrapper: state-sanitize.

On Unix: delegates to state-sanitize.sh.
On Windows: native Python implementation.

Claude Code Hook Protocol:
  Receives JSON on stdin: {"tool_name": "...", "tool_input": {...}}
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
        script = HOOK_DIR / "state-sanitize.sh"
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

    # Normalize tool_name for check.py routing
    try:
        data = json.loads(stdin_data)
        data["tool_name"] = "workflow_state_save"
        normalized_input = json.dumps(data)
    except (json.JSONDecodeError, KeyError):
        block("Security check failed: input normalization error")
        return

    try:
        result = subprocess.run(
            [sys.executable, "-m", "spellbook_mcp.security.check"],
            input=normalized_input,
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "PYTHONPATH": project_root},
            cwd=project_root,
        )
    except (OSError, subprocess.TimeoutExpired):
        block("Security check failed: internal error")
        return

    if result.returncode == 0:
        sys.exit(0)
    elif result.returncode == 2:
        if result.stdout.strip():
            print(result.stdout.strip())
        else:
            print(json.dumps({"error": "Security check failed: injection pattern detected in workflow state"}))
        sys.exit(2)
    else:
        block("Security check failed: internal error")
        return


if __name__ == "__main__":
    main()
