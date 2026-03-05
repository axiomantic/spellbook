#!/usr/bin/env python3
"""PostToolUse hook: Send OS notification when tools exceed threshold.

Reads and deletes /tmp/claude-notify-start-{tool_use_id} (or %TEMP% on Windows).
Calls platform notification tools directly -- no HTTP round-trip.

On non-Windows: delegates to notify-on-complete.sh via os.execv.
On Windows: uses PowerShell toast notifications.

Claude Code Hook Protocol (PostToolUse):
  Receives JSON on stdin: {"tool_name": "...", "tool_input": {...}, ...}
  Exit 0: always (notification hook, never blocks)

FAILURE POLICY: FAIL-OPEN
  Notification failures must NEVER prevent tool execution.
"""

import json
import os
import sys
import tempfile
import time


def main() -> None:
    # On non-Windows, delegate to shell script
    if sys.platform != "win32":
        script_dir = os.path.dirname(os.path.abspath(__file__))
        shell_script = os.path.join(script_dir, "notify-on-complete.sh")
        if os.path.exists(shell_script):
            os.execv("/usr/bin/env", ["/usr/bin/env", "bash", shell_script])
        sys.exit(0)

    # -----------------------------------------------------------------------
    # Windows path
    # -----------------------------------------------------------------------
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_use_id = data.get("tool_use_id", "")

    # Validate tool_use_id against path traversal and whitespace
    if (
        not tool_use_id
        or "/" in tool_use_id
        or ".." in tool_use_id
        or any(c.isspace() for c in tool_use_id)
    ):
        sys.exit(0)

    # Check if notifications are enabled
    if os.environ.get("SPELLBOOK_NOTIFY_ENABLED", "true").lower() != "true":
        sys.exit(0)

    # Tool blacklist: interactive tools that should NOT trigger notifications
    blacklist = {
        "AskUserQuestion",
        "TodoRead",
        "TodoWrite",
        "TaskCreate",
        "TaskUpdate",
        "TaskGet",
        "TaskList",
    }
    if tool_name in blacklist:
        sys.exit(0)

    # Read and delete our timer file
    temp_dir = tempfile.gettempdir()
    start_file = os.path.join(temp_dir, f"claude-notify-start-{tool_use_id}")
    if not os.path.exists(start_file):
        sys.exit(0)

    try:
        with open(start_file) as f:
            start_time = int(f.read().strip())
        os.unlink(start_file)
    except (OSError, ValueError):
        sys.exit(0)

    # Check threshold
    elapsed = int(time.time()) - start_time
    threshold = int(os.environ.get("SPELLBOOK_NOTIFY_THRESHOLD", "30"))
    if elapsed < threshold:
        sys.exit(0)

    # Build notification content
    title = os.environ.get("SPELLBOOK_NOTIFY_TITLE", "Spellbook")
    body = f"{tool_name} finished ({elapsed}s)"

    # Sanitize for PowerShell single quotes
    safe_title = title.replace("'", "''")
    safe_body = body.replace("'", "''")

    # Send Windows toast notification via PowerShell
    import subprocess

    # Prefer pwsh (PowerShell Core) over legacy powershell
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    pwsh_path = os.path.join(system_root, "System32", "pwsh.exe")
    shell = "pwsh" if os.path.exists(pwsh_path) else "powershell"

    ps_script = f"""
    try {{
        Import-Module BurntToast -ErrorAction Stop
        New-BurntToastNotification -Text '{safe_title}','{safe_body}'
    }} catch {{
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName('text')
        $textNodes.Item(0).AppendChild($template.CreateTextNode('{safe_title}')) | Out-Null
        $textNodes.Item(1).AppendChild($template.CreateTextNode('{safe_body}')) | Out-Null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Spellbook').Show($toast)
    }}
    """

    # No check=True: fail-open policy for hooks
    subprocess.run(
        [shell, "-Command", ps_script],
        capture_output=True,
        timeout=10,
    )


if __name__ == "__main__":
    main()
