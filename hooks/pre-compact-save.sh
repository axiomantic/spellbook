#!/usr/bin/env bash
# pre-compact-save.sh - PreCompact hook to save workflow state before compaction
#
# Claude Code Hook Protocol (PreCompact):
#   Receives JSON on stdin:
#     {"session_id":"abc","transcript_path":"/path/to/session.jsonl",
#      "cwd":"/project/path","permission_mode":"default",
#      "hook_event_name":"PreCompact","trigger":"auto","custom_instructions":""}
#   Exit 0: always (never block compaction)
#
# FAILURE POLICY: FAIL-OPEN
#   State save failures must NEVER prevent compaction. All error paths
#   exit 0. This is critical - blocking compaction would freeze the session.
#
# Flow:
#   1. Read stdin JSON, extract cwd as project path
#   2. Check if MCP daemon is reachable
#   3. Call workflow_state_load to check if state is already fresh (< 5 min)
#   4. If fresh, exit early (nothing to do)
#   5. If stale or not found, call workflow_state_save with trigger="auto"
#   6. Exit 0 always

set -euo pipefail

# ---------------------------------------------------------------------------
# Fail-open trap: ensure we NEVER block compaction
# ---------------------------------------------------------------------------
trap 'exit 0' ERR

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MCP_HOST="${SPELLBOOK_MCP_HOST:-127.0.0.1}"
MCP_PORT="${SPELLBOOK_MCP_PORT:-8765}"
MCP_URL="http://${MCP_HOST}:${MCP_PORT}/mcp"
LOG_DIR="${HOME}/.local/spellbook/logs"
LOG_FILE="${LOG_DIR}/pre-compact.log"

# Create log directory if needed
mkdir -p "${LOG_DIR}" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Logging helper (append to log file, never stderr - stderr shows to user)
# ---------------------------------------------------------------------------
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [pre-compact-save] $*" >> "${LOG_FILE}" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Read stdin JSON
# ---------------------------------------------------------------------------
INPUT="$(cat)"
if [[ -z "${INPUT}" ]]; then
    log "Empty stdin, exiting"
    exit 0
fi

# ---------------------------------------------------------------------------
# Extract project path from cwd field
# ---------------------------------------------------------------------------
PROJECT_PATH=$(python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read())
    print(d.get('cwd', ''))
except Exception:
    print('')
" <<< "${INPUT}" 2>/dev/null) || { log "Failed to parse stdin JSON"; exit 0; }

if [[ -z "${PROJECT_PATH}" ]]; then
    log "No cwd in stdin JSON, exiting"
    exit 0
fi

log "Project path: ${PROJECT_PATH}"

# ---------------------------------------------------------------------------
# MCP HTTP helper: call an MCP tool via the daemon's HTTP endpoint
# Returns the tool result JSON on stdout, or empty string on failure
# ---------------------------------------------------------------------------
mcp_call() {
    local tool_name="$1"
    local arguments="$2"

    local body
    body=$(python3 -c "
import json
print(json.dumps({
    'jsonrpc': '2.0',
    'id': 1,
    'method': 'tools/call',
    'params': {
        'name': '${tool_name}',
        'arguments': json.loads('''${arguments}''')
    }
}))
" 2>/dev/null) || { log "Failed to build MCP request for ${tool_name}"; return 1; }

    local response
    response=$(curl -s \
        --connect-timeout 0.5 \
        --max-time 1.5 \
        -X POST "${MCP_URL}" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d "${body}" 2>/dev/null) || { log "curl failed for ${tool_name}"; return 1; }

    # Parse SSE response: extract data lines and find the result
    local result
    result=$(python3 -c "
import json, sys

raw = sys.stdin.read()
# SSE format: look for 'data: ' lines
result = None
for line in raw.split('\n'):
    line = line.strip()
    if line.startswith('data: '):
        try:
            parsed = json.loads(line[6:])
            # Look for the result in the JSON-RPC response
            if 'result' in parsed:
                sc = parsed['result'].get('structuredContent')
                if sc is not None:
                    result = sc
                    break
                # Also check content array (some tools return here)
                content = parsed['result'].get('content', [])
                for item in content:
                    if item.get('type') == 'text':
                        try:
                            result = json.loads(item['text'])
                            break
                        except (json.JSONDecodeError, KeyError):
                            pass
                if result:
                    break
        except json.JSONDecodeError:
            continue

if result is not None:
    print(json.dumps(result))
else:
    print('')
" <<< "${response}" 2>/dev/null) || { log "Failed to parse MCP response for ${tool_name}"; return 1; }

    if [[ -z "${result}" ]]; then
        log "Empty result from ${tool_name}"
        return 1
    fi

    echo "${result}"
}

# ---------------------------------------------------------------------------
# Step 1: Check if daemon is reachable by loading current state
# ---------------------------------------------------------------------------
log "Checking for existing workflow state"

LOAD_RESULT=$(mcp_call "workflow_state_load" "{\"project_path\": \"${PROJECT_PATH}\", \"max_age_hours\": 24}") || {
    log "MCP daemon unreachable or workflow_state_load failed, exiting"
    exit 0
}

# ---------------------------------------------------------------------------
# Step 2: Check if state is fresh enough (< 5 minutes = 0.083 hours)
# ---------------------------------------------------------------------------
IS_FRESH=$(python3 -c "
import json, sys
try:
    result = json.loads(sys.stdin.read())
    found = result.get('found', False)
    age = result.get('age_hours')
    if found and age is not None and float(age) < 0.083:
        print('true')
    else:
        print('false')
except Exception:
    print('false')
" <<< "${LOAD_RESULT}" 2>/dev/null) || IS_FRESH="false"

if [[ "${IS_FRESH}" == "true" ]]; then
    log "Workflow state is fresh (< 5 min old), nothing to do"
    exit 0
fi

# ---------------------------------------------------------------------------
# Step 3: Save minimal workflow state with trigger="auto"
# Build state from what we know (project path, timestamp)
# ---------------------------------------------------------------------------
log "Saving workflow state (trigger=auto)"

SAVE_ARGS=$(python3 -c "
import json, sys
try:
    # Try to extract existing state to preserve it
    load_result = json.loads(sys.stdin.read())
    existing_state = load_result.get('state') or {}
except Exception:
    existing_state = {}

# Merge with minimal required fields
state = dict(existing_state)
if 'compaction_flag' not in state:
    state['compaction_flag'] = True

args = {
    'project_path': '${PROJECT_PATH}',
    'state': state,
    'trigger': 'auto'
}
print(json.dumps(args))
" <<< "${LOAD_RESULT}" 2>/dev/null) || {
    log "Failed to build save arguments"
    exit 0
}

SAVE_RESULT=$(mcp_call "workflow_state_save" "${SAVE_ARGS}") || {
    log "workflow_state_save failed"
    exit 0
}

log "Save result: ${SAVE_RESULT}"
log "Pre-compact save complete"
exit 0
