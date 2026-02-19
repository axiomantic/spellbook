#!/usr/bin/env bash
# state-sanitize.sh - PreToolUse hook for workflow_state_save
#
# Claude Code Hook Protocol:
#   Receives JSON on stdin: {"tool_name": "...", "tool_input": {...}}
#   Exit 0: allow the tool call
#   Exit 2: block the tool call (stdout JSON: {"error": "reason"})
#   Any other failure: block (fail-closed)
#
# This hook delegates validation to spellbook_mcp.security.check, which
# extracts all string values from the workflow state and checks for
# injection patterns. Error messages never include blocked content to
# prevent reflection attacks.

set -euo pipefail

# ---------------------------------------------------------------------------
# Debug logging (only when SPELLBOOK_SECURITY_DEBUG is set and non-empty)
# ---------------------------------------------------------------------------
debug() {
    if [[ -n "${SPELLBOOK_SECURITY_DEBUG:-}" ]]; then
        echo "[state-sanitize] $*" >&2
    fi
}

# ---------------------------------------------------------------------------
# Fail-closed helper: block with a generic error, never echoing user content
# ---------------------------------------------------------------------------
block() {
    local reason="${1:-Security check unavailable}"
    echo "{\"error\": \"${reason}\"}"
    exit 2
}

# ---------------------------------------------------------------------------
# Locate the spellbook project root so we can find spellbook_mcp
# ---------------------------------------------------------------------------
if [[ -n "${SPELLBOOK_DIR:-}" ]]; then
    PROJECT_ROOT="${SPELLBOOK_DIR}"
    debug "Using SPELLBOOK_DIR=${PROJECT_ROOT}"
else
    # Derive from script location: hooks/ is one level below project root
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
    debug "Derived PROJECT_ROOT=${PROJECT_ROOT}"
fi

# ---------------------------------------------------------------------------
# Verify Python is available
# ---------------------------------------------------------------------------
if ! command -v python3 &>/dev/null; then
    debug "python3 not found on PATH"
    block "Security check failed: python3 not available"
fi

# ---------------------------------------------------------------------------
# Verify the security check module exists
# ---------------------------------------------------------------------------
if [[ ! -f "${PROJECT_ROOT}/spellbook_mcp/security/check.py" ]]; then
    debug "check.py not found at ${PROJECT_ROOT}/spellbook_mcp/security/check.py"
    block "Security check failed: check module not found"
fi

# ---------------------------------------------------------------------------
# Read JSON from stdin
# ---------------------------------------------------------------------------
INPUT="$(cat)"
debug "Received input (${#INPUT} bytes)"

if [[ -z "${INPUT}" ]]; then
    debug "Empty stdin"
    block "Security check failed: no input received"
fi

# ---------------------------------------------------------------------------
# Normalize tool_name for check.py routing
# ---------------------------------------------------------------------------
# Claude Code sends the full MCP tool name (e.g., "mcp__spellbook__workflow_state_save")
# but check.py routes on bare names (e.g., "workflow_state_save"). Normalize to
# ensure correct rule routing.
NORMALIZED_INPUT="$(python3 -c "
import json, sys
try:
    data = json.loads(sys.stdin.read())
    data['tool_name'] = 'workflow_state_save'
    print(json.dumps(data))
except Exception:
    sys.exit(1)
" <<< "${INPUT}" 2>/dev/null)" || {
    debug "Failed to normalize tool_name"
    block "Security check failed: input normalization error"
}

# ---------------------------------------------------------------------------
# Invoke the security check module
# ---------------------------------------------------------------------------
debug "Running security check"

# Run check.py, capturing stdout and exit code separately.
# PYTHONPATH ensures the module can be imported from the project root.
set +e
CHECK_OUTPUT="$(echo "${NORMALIZED_INPUT}" | PYTHONPATH="${PROJECT_ROOT}" python3 -m spellbook_mcp.security.check 2>>"${SPELLBOOK_SECURITY_LOG:-/dev/null}")"
CHECK_EXIT=$?
set -e

debug "check.py exited with code ${CHECK_EXIT}"

case ${CHECK_EXIT} in
    0)
        # Safe: allow the tool call
        debug "Allowing tool call"
        exit 0
        ;;
    2)
        # Blocked by check.py: forward its structured error
        debug "Tool call blocked by check.py"
        if [[ -n "${CHECK_OUTPUT}" ]]; then
            echo "${CHECK_OUTPUT}"
        else
            echo '{"error": "Security check failed: injection pattern detected in workflow state"}'
        fi
        exit 2
        ;;
    *)
        # Any other exit code: fail-closed with generic message
        debug "check.py failed unexpectedly (exit ${CHECK_EXIT}), blocking"
        block "Security check failed: internal error"
        ;;
esac
