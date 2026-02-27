#!/usr/bin/env bash
# tts-notify.sh - PostToolUse hook for TTS notifications
#
# Claude Code Hook Protocol (PostToolUse):
#   Receives JSON on stdin: {"tool_name":"...","tool_input":{...},
#     "tool_use_id":"...","session_id":"...","cwd":"...",
#     "transcript_path":"..."}
#   Exit 0: always (notification hook, never blocks)
#
# FAILURE POLICY: FAIL-OPEN
#   TTS failures must NEVER prevent tool execution.
#
# Sends POST to MCP server's /api/speak endpoint.
# Falls back silently if MCP server not running.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
THRESHOLD="${SPELLBOOK_TTS_THRESHOLD:-30}"
MCP_PORT="${SPELLBOOK_MCP_PORT:-8765}"
MCP_HOST="${SPELLBOOK_MCP_HOST:-127.0.0.1}"
SPEAK_URL="http://${MCP_HOST}:${MCP_PORT}/api/speak"

# ---------------------------------------------------------------------------
# Tool blacklist: interactive tools that should NOT trigger notifications
# ---------------------------------------------------------------------------
BLACKLIST="AskUserQuestion|TodoRead|TodoWrite|TaskCreate|TaskUpdate|TaskGet|TaskList"

# ---------------------------------------------------------------------------
# Read stdin
# ---------------------------------------------------------------------------
INPUT="$(cat)"
if [[ -z "${INPUT}" ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Extract fields with lightweight JSON parsing
# ---------------------------------------------------------------------------
TOOL_NAME=$(echo "${INPUT}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(d.get('tool_name', ''))
" 2>/dev/null) || exit 0

# Check blacklist
if echo "${TOOL_NAME}" | grep -qE "^(${BLACKLIST})$"; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Timing check: skip if under threshold
# ---------------------------------------------------------------------------
TOOL_USE_ID=$(echo "${INPUT}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(d.get('tool_use_id', ''))
" 2>/dev/null) || exit 0

START_FILE="/tmp/claude-tool-start-${TOOL_USE_ID}"
if [[ ! -f "${START_FILE}" ]]; then
    exit 0
fi

START_TS=$(cat "${START_FILE}" 2>/dev/null) || exit 0
rm -f "${START_FILE}"

NOW=$(date +%s)
ELAPSED=$((NOW - START_TS))
if [[ ${ELAPSED} -lt ${THRESHOLD} ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Build announcement message
# ---------------------------------------------------------------------------
MESSAGE=$(echo "${INPUT}" | python3 -c "
import json, os, shlex, sys
d = json.load(sys.stdin)
tool = d.get('tool_name', 'unknown')
cwd = d.get('cwd', '')
project = os.path.basename(cwd) if cwd else 'unknown'

# Detail extraction
inp = d.get('tool_input') or {}
detail = ''
if tool == 'Bash':
    cmd = inp.get('command', '')
    if cmd:
        try: detail = shlex.split(cmd)[0].split('/')[-1]
        except: detail = cmd.split()[0].split('/')[-1] if cmd.split() else ''
elif tool == 'Task':
    detail = inp.get('description', '')[:40]

parts = [project, tool]
if detail:
    parts.append(detail)
parts.append('finished')
print(' '.join(parts))
" 2>/dev/null) || exit 0

if [[ -z "${MESSAGE}" ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Send to MCP server (fail silently)
# ---------------------------------------------------------------------------
curl -s -m 5 -X POST "${SPEAK_URL}" \
    -H "Content-Type: application/json" \
    -d "{\"text\": $(echo "${MESSAGE}" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))')}" \
    >/dev/null 2>&1 || true

exit 0
