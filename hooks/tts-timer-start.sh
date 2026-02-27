#!/usr/bin/env bash
# tts-timer-start.sh - PreToolUse hook for recording tool start times
#
# Claude Code Hook Protocol (PreToolUse):
#   Receives JSON on stdin: {"tool_name":"...","tool_input":{...},
#     "tool_use_id":"...","session_id":"...","cwd":"...",
#     "transcript_path":"..."}
#   Exit 0: allow tool execution (this hook NEVER blocks)
#
# FAILURE POLICY: FAIL-OPEN
#   Timing failures must NEVER prevent tool execution.
#
# Writes current Unix timestamp to /tmp/claude-tool-start-{tool_use_id}.
# The companion tts-notify.sh PostToolUse hook reads and deletes this file.

set -euo pipefail

# ---------------------------------------------------------------------------
# Read stdin
# ---------------------------------------------------------------------------
INPUT="$(cat)"
if [[ -z "${INPUT}" ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Extract tool_use_id
# ---------------------------------------------------------------------------
TOOL_USE_ID=$(echo "${INPUT}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(d.get('tool_use_id', ''))
" 2>/dev/null) || exit 0

if [[ -z "${TOOL_USE_ID}" ]]; then
    exit 0
fi

if [[ "${TOOL_USE_ID}" =~ [/[:space:]] ]] || [[ "${TOOL_USE_ID}" == *..* ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Write start timestamp (fail silently)
# ---------------------------------------------------------------------------
date +%s > "/tmp/claude-tool-start-${TOOL_USE_ID}" 2>/dev/null || true

exit 0
