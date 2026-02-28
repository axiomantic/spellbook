#!/usr/bin/env python3
"""Cross-platform hook wrapper: tts-notify.

On Unix: delegates to tts-notify.sh.
On Windows: native Python implementation.

Claude Code Hook Protocol (PostToolUse):
  Receives JSON on stdin: {"tool_name": "...", "tool_input": {...}, ...}
  Exit 0: always (notification hook, never blocks)

FAILURE POLICY: FAIL-OPEN
"""
import json
import os
import shlex
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HOOK_DIR = Path(__file__).parent


def main() -> None:
    if sys.platform != "win32":
        script = HOOK_DIR / "tts-notify.sh"
        os.execv("/bin/bash", ["bash", str(script)] + sys.argv[1:])

    # Windows: native Python implementation
    threshold = int(os.environ.get("SPELLBOOK_TTS_THRESHOLD", "30"))
    mcp_port = os.environ.get("SPELLBOOK_MCP_PORT", "8765")
    mcp_host = os.environ.get("SPELLBOOK_MCP_HOST", "127.0.0.1")
    speak_url = f"http://{mcp_host}:{mcp_port}/api/speak"

    blacklist = {
        "AskUserQuestion", "TodoRead", "TodoWrite",
        "TaskCreate", "TaskUpdate", "TaskGet", "TaskList",
    }

    stdin_data = sys.stdin.read()
    if not stdin_data:
        sys.exit(0)

    try:
        data = json.loads(stdin_data)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name in blacklist:
        sys.exit(0)

    tool_use_id = data.get("tool_use_id", "")
    if not tool_use_id:
        sys.exit(0)

    start_file = Path(tempfile.gettempdir()) / f"claude-tool-start-{tool_use_id}"
    try:
        start_ts = int(start_file.read_text().strip())
        start_file.unlink()
    except (FileNotFoundError, ValueError):
        sys.exit(0)

    elapsed = int(time.time()) - start_ts
    if elapsed < threshold:
        sys.exit(0)

    # Build message
    cwd = data.get("cwd", "")
    project = os.path.basename(cwd) if cwd else "unknown"

    # Detail extraction (matches tts-notify.sh logic)
    inp = data.get("tool_input") or {}
    detail = ""
    if tool_name == "Bash":
        cmd = inp.get("command", "")
        if cmd:
            try:
                parts_cmd = shlex.split(cmd)
            except ValueError:
                parts_cmd = cmd.split()
            detail = parts_cmd[0].split("/")[-1] if parts_cmd else ""
    elif tool_name == "Task":
        detail = inp.get("description", "")[:40]

    parts = [project, tool_name]
    if detail:
        parts.append(detail)
    parts.append("finished")
    message = " ".join(parts)

    # Send to MCP server
    try:
        payload = json.dumps({"text": message}).encode()
        req = urllib.request.Request(
            speak_url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass  # Fail-open

    sys.exit(0)


if __name__ == "__main__":
    main()
