#!/usr/bin/env bash
# post-compact-recover.sh - SessionStart hook for post-compaction recovery
#
# Claude Code Hook Protocol (SessionStart):
#   Receives JSON on stdin:
#     {"session_id":"abc","transcript_path":"/path/to/session.jsonl",
#      "cwd":"/project/path","permission_mode":"default",
#      "hook_event_name":"SessionStart","source":"compact","model":"claude-sonnet-4-6"}
#   Output JSON to stdout:
#     {"hookSpecificOutput":{"hookEventName":"SessionStart",
#      "additionalContext":"<recovery directive>"}}
#   Exit 0: always (never prevent session start)
#
# FAILURE POLICY: FAIL-OPEN
#   Recovery failures must NEVER prevent the session from starting.
#   On any error, output a minimal fallback directive and exit 0.
#
# Flow:
#   1. Read stdin JSON, extract cwd and source
#   2. Verify source == "compact" (safety check)
#   3. Call workflow_state_load via MCP HTTP
#   4. If state found with active skill, call skill_instructions_get
#   5. Build recovery directive with skill constraints
#   6. Output as hookSpecificOutput JSON to stdout
#   7. If daemon unreachable, output minimal fallback directive

set -euo pipefail

# ---------------------------------------------------------------------------
# Fail-open trap: output fallback directive on any error
# ---------------------------------------------------------------------------
output_fallback() {
    local msg="COMPACTION OCCURRED. Call spellbook_session_init to restore workflow state."
    python3 -c "
import json
output = {
    'hookSpecificOutput': {
        'hookEventName': 'SessionStart',
        'additionalContext': '${msg}'
    }
}
print(json.dumps(output))
" 2>/dev/null || echo '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"COMPACTION OCCURRED. Call spellbook_session_init to restore workflow state."}}'
    exit 0
}

trap 'output_fallback' ERR

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MCP_HOST="${SPELLBOOK_MCP_HOST:-127.0.0.1}"
MCP_PORT="${SPELLBOOK_MCP_PORT:-8765}"
MCP_URL="http://${MCP_HOST}:${MCP_PORT}/mcp"
LOG_DIR="${HOME}/.local/spellbook/logs"
LOG_FILE="${LOG_DIR}/post-compact-recover.log"

# Create log directory if needed
mkdir -p "${LOG_DIR}" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Logging helper (append to log file, never stderr - stderr shows to user)
# ---------------------------------------------------------------------------
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [post-compact-recover] $*" >> "${LOG_FILE}" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Read stdin JSON
# ---------------------------------------------------------------------------
INPUT="$(cat)"
if [[ -z "${INPUT}" ]]; then
    log "Empty stdin, outputting fallback"
    output_fallback
fi

# ---------------------------------------------------------------------------
# Extract fields: cwd, source
# ---------------------------------------------------------------------------
PARSED=$(python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read())
    print(d.get('cwd', ''))
    print(d.get('source', ''))
except Exception:
    print('')
    print('')
" <<< "${INPUT}" 2>/dev/null) || { log "Failed to parse stdin"; output_fallback; }

PROJECT_PATH=$(echo "${PARSED}" | head -1)
SOURCE=$(echo "${PARSED}" | tail -1)

if [[ -z "${PROJECT_PATH}" ]]; then
    log "No cwd in stdin JSON"
    output_fallback
fi

# ---------------------------------------------------------------------------
# Safety check: verify source is "compact"
# The matcher should already filter, but defense-in-depth
# ---------------------------------------------------------------------------
if [[ "${SOURCE}" != "compact" ]]; then
    log "Source is '${SOURCE}', not 'compact' - exiting without directive"
    exit 0
fi

log "Post-compaction recovery for: ${PROJECT_PATH}"

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
        --max-time 2 \
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
            if 'result' in parsed:
                sc = parsed['result'].get('structuredContent')
                if sc is not None:
                    result = sc
                    break
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
# Step 1: Load workflow state
# ---------------------------------------------------------------------------
log "Loading workflow state"

LOAD_RESULT=$(mcp_call "workflow_state_load" "{\"project_path\": \"${PROJECT_PATH}\", \"max_age_hours\": 24}") || {
    log "MCP daemon unreachable, outputting fallback directive"
    output_fallback
}

# ---------------------------------------------------------------------------
# Step 2: Extract state details for the recovery directive
# ---------------------------------------------------------------------------
STATE_INFO=$(python3 -c "
import json, sys
try:
    result = json.loads(sys.stdin.read())
    found = result.get('found', False)
    state = result.get('state') or {}

    info = {
        'found': found,
        'active_skill': state.get('active_skill', ''),
        'skill_phase': state.get('skill_phase', ''),
        'binding_decisions': state.get('binding_decisions', []),
        'next_action': state.get('next_action', ''),
        'workflow_pattern': state.get('workflow_pattern', ''),
    }
    print(json.dumps(info))
except Exception as e:
    print(json.dumps({'found': False}))
" <<< "${LOAD_RESULT}" 2>/dev/null) || STATE_INFO='{"found": false}'

HAS_STATE=$(python3 -c "
import json, sys
info = json.loads(sys.stdin.read())
print('true' if info.get('found') else 'false')
" <<< "${STATE_INFO}" 2>/dev/null) || HAS_STATE="false"

if [[ "${HAS_STATE}" != "true" ]]; then
    log "No workflow state found, outputting minimal directive"
    output_fallback
fi

# ---------------------------------------------------------------------------
# Step 3: If we have an active skill, fetch its FORBIDDEN/REQUIRED sections
# ---------------------------------------------------------------------------
ACTIVE_SKILL=$(python3 -c "
import json, sys
info = json.loads(sys.stdin.read())
print(info.get('active_skill', ''))
" <<< "${STATE_INFO}" 2>/dev/null) || ACTIVE_SKILL=""

SKILL_CONSTRAINTS=""
if [[ -n "${ACTIVE_SKILL}" ]]; then
    log "Fetching skill constraints for: ${ACTIVE_SKILL}"

    SKILL_ARGS=$(python3 -c "
import json
print(json.dumps({
    'skill_name': '${ACTIVE_SKILL}',
    'sections': ['FORBIDDEN', 'REQUIRED']
}))
" 2>/dev/null) || SKILL_ARGS=""

    if [[ -n "${SKILL_ARGS}" ]]; then
        SKILL_RESULT=$(mcp_call "skill_instructions_get" "${SKILL_ARGS}") || {
            log "skill_instructions_get failed for ${ACTIVE_SKILL}"
            SKILL_RESULT=""
        }

        if [[ -n "${SKILL_RESULT}" ]]; then
            SKILL_CONSTRAINTS=$(python3 -c "
import json, sys
try:
    result = json.loads(sys.stdin.read())
    if result.get('success'):
        sections = result.get('sections', {})
        parts = []
        forbidden = sections.get('FORBIDDEN', '')
        required = sections.get('REQUIRED', '')
        if forbidden:
            parts.append('**FORBIDDEN:**\n' + forbidden)
        if required:
            parts.append('**REQUIRED:**\n' + required)
        print('\n\n'.join(parts))
    else:
        print('')
except Exception:
    print('')
" <<< "${SKILL_RESULT}" 2>/dev/null) || SKILL_CONSTRAINTS=""
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Step 4: Build the recovery directive
# ---------------------------------------------------------------------------
log "Building recovery directive"

DIRECTIVE=$(python3 -c "
import json, sys

state_info = json.loads('''${STATE_INFO}''')
skill_constraints = '''${SKILL_CONSTRAINTS}'''

parts = []
parts.append('## POST-COMPACTION RECOVERY DIRECTIVE')
parts.append('')
parts.append('**CRITICAL**: Context was just compacted. You MUST take these actions IMMEDIATELY, before ANY other work:')
parts.append('')
parts.append('1. Call \`spellbook_session_init\` MCP tool')
parts.append('2. Execute the returned \`resume_boot_prompt\` completely')
parts.append('3. Do NOT implement code directly - you are an ORCHESTRATOR')
parts.append('')

active_skill = state_info.get('active_skill', '')
skill_phase = state_info.get('skill_phase', '')
workflow_pattern = state_info.get('workflow_pattern', '')

if active_skill or skill_phase:
    parts.append('### Active Workflow')
    if active_skill:
        parts.append(f'- **Skill**: {active_skill}')
    if skill_phase:
        parts.append(f'- **Phase**: {skill_phase}')
    if workflow_pattern:
        parts.append(f'- **Pattern**: {workflow_pattern}')
    parts.append('')

if skill_constraints:
    parts.append('### Skill Constraints')
    parts.append(skill_constraints)
    parts.append('')

binding_decisions = state_info.get('binding_decisions', [])
if binding_decisions:
    parts.append('### Binding Decisions (DO NOT REVISIT)')
    for decision in binding_decisions:
        if isinstance(decision, str):
            parts.append(f'- {decision}')
        elif isinstance(decision, dict):
            desc = decision.get('description', decision.get('decision', str(decision)))
            parts.append(f'- {desc}')
    parts.append('')

next_action = state_info.get('next_action', '')
if next_action:
    parts.append('### Next Action')
    parts.append(next_action)
    parts.append('')

print('\n'.join(parts))
" 2>/dev/null) || {
    log "Failed to build directive"
    output_fallback
}

if [[ -z "${DIRECTIVE}" ]]; then
    log "Empty directive, using fallback"
    output_fallback
fi

# ---------------------------------------------------------------------------
# Step 5: Output as hookSpecificOutput JSON
# ---------------------------------------------------------------------------
python3 -c "
import json, sys

directive = sys.stdin.read()
output = {
    'hookSpecificOutput': {
        'hookEventName': 'SessionStart',
        'additionalContext': directive
    }
}
print(json.dumps(output))
" <<< "${DIRECTIVE}" 2>/dev/null || {
    log "Failed to JSON-encode output"
    output_fallback
}

log "Recovery directive output successfully"
exit 0
