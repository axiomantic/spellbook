#!/usr/bin/env bash
# notify-on-complete.sh - PostToolUse hook for OS notifications
#
# Claude Code Hook Protocol (PostToolUse):
#   Receives JSON on stdin: {"tool_name":"...","tool_input":{...},
#     "tool_use_id":"...","session_id":"...","cwd":"...",
#     "transcript_path":"..."}
#   Exit 0: always (notification hook, never blocks)
#
# FAILURE POLICY: FAIL-OPEN
#   Notification failures must NEVER prevent tool execution.
#
# Calls osascript (macOS) or notify-send (Linux) directly -- no HTTP round-trip.
# Reads and deletes /tmp/claude-notify-start-{tool_use_id}.

set -euo pipefail

# ---------------------------------------------------------------------------
# Read hook input from stdin
# ---------------------------------------------------------------------------
INPUT=$(cat)

# ---------------------------------------------------------------------------
# Extract fields
# ---------------------------------------------------------------------------
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
TOOL_USE_ID=$(echo "$INPUT" | jq -r '.tool_use_id // empty')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

# ---------------------------------------------------------------------------
# Validate tool_use_id against path traversal
# ---------------------------------------------------------------------------
if [[ -z "$TOOL_USE_ID" ]] || [[ "$TOOL_USE_ID" =~ [/[:space:]] ]] || [[ "$TOOL_USE_ID" == *..* ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Check if notifications are enabled (env var, default true)
# ---------------------------------------------------------------------------
NOTIFY_ENABLED="${SPELLBOOK_NOTIFY_ENABLED:-true}"
if [[ "$NOTIFY_ENABLED" != "true" ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Tool blacklist: interactive tools that should NOT trigger notifications
# ---------------------------------------------------------------------------
case "$TOOL_NAME" in
    AskUserQuestion|TodoRead|TodoWrite|TaskCreate|TaskUpdate|TaskGet|TaskList)
        exit 0
        ;;
esac

# ---------------------------------------------------------------------------
# Read and delete our timer file
# ---------------------------------------------------------------------------
START_FILE="/tmp/claude-notify-start-${TOOL_USE_ID}"
if [[ ! -f "$START_FILE" ]]; then
    exit 0
fi
START_TIME=$(cat "$START_FILE" 2>/dev/null || echo "")
rm -f "$START_FILE"

if [[ -z "$START_TIME" ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Check threshold
# ---------------------------------------------------------------------------
NOW=$(date +%s)
ELAPSED=$((NOW - START_TIME))
THRESHOLD="${SPELLBOOK_NOTIFY_THRESHOLD:-30}"
if [[ $ELAPSED -lt $THRESHOLD ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Build notification content
# ---------------------------------------------------------------------------
NOTIFY_TITLE="${SPELLBOOK_NOTIFY_TITLE:-Spellbook}"
# Sanitize title for AppleScript (strip double quotes)
NOTIFY_TITLE=$(echo "$NOTIFY_TITLE" | tr -d '"')
BODY="${TOOL_NAME} finished (${ELAPSED}s)"

# ---------------------------------------------------------------------------
# Send platform-specific notification
# ---------------------------------------------------------------------------
if [[ "$(uname)" == "Darwin" ]]; then
    osascript -e "display notification \"${BODY}\" with title \"${NOTIFY_TITLE}\"" 2>/dev/null || true
elif command -v notify-send >/dev/null 2>&1; then
    notify-send "$NOTIFY_TITLE" "$BODY" 2>/dev/null || true
fi

exit 0
