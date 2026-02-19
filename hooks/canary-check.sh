#!/usr/bin/env bash
# canary-check.sh - PostToolUse hook for canary token detection
#
# Claude Code Hook Protocol (PostToolUse):
#   Receives JSON on stdin: {"tool_name": "...", "tool_input": {...}, "tool_output": "..."}
#   Exit 0: always (this hook NEVER blocks tool execution)
#
# FAILURE POLICY: FAIL-OPEN
#   Canary check failures must NEVER prevent tool execution. All error paths
#   exit 0 with a stderr warning. This is the opposite of fail-closed
#   hooks like bash-gate.sh and spawn-guard.sh.
#
# This hook delegates canary scanning to spellbook_mcp.security.check --mode canary,
# which scans tool output for registered canary tokens.
# Error messages never include input content to prevent reflection attacks.

set -euo pipefail

# ---------------------------------------------------------------------------
# Debug logging (only when SPELLBOOK_DEBUG is set and non-empty)
# ---------------------------------------------------------------------------
debug() {
    if [[ -n "${SPELLBOOK_DEBUG:-}" ]]; then
        echo "[canary-check] $*" >&2
    fi
}

# ---------------------------------------------------------------------------
# Fail-open helper: warn on stderr but always exit 0
# ---------------------------------------------------------------------------
warn_and_continue() {
    local reason="${1:-Canary check unavailable}"
    echo "[canary-check] WARNING: ${reason}" >&2
    exit 0
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
# Verify Python is available (fail-open if missing)
# ---------------------------------------------------------------------------
if ! command -v python3 &>/dev/null; then
    debug "python3 not found on PATH"
    warn_and_continue "python3 not available"
fi

# ---------------------------------------------------------------------------
# Verify the security check module exists (fail-open if missing)
# ---------------------------------------------------------------------------
if [[ ! -f "${PROJECT_ROOT}/spellbook_mcp/security/check.py" ]]; then
    debug "check.py not found at ${PROJECT_ROOT}/spellbook_mcp/security/check.py"
    warn_and_continue "check module not found"
fi

# ---------------------------------------------------------------------------
# Read JSON from stdin (fail-open on empty input)
# ---------------------------------------------------------------------------
INPUT="$(cat)"
debug "Received input (${#INPUT} bytes)"

if [[ -z "${INPUT}" ]]; then
    debug "Empty stdin"
    warn_and_continue "no input received"
fi

# ---------------------------------------------------------------------------
# Invoke the security check module in canary mode
# ---------------------------------------------------------------------------
debug "Running canary check"

# Run check.py with --mode canary, capturing exit code.
# PYTHONPATH ensures the module can be imported from the project root.
# Canary mode is fail-open: check.py --mode canary always exits 0.
# stderr passes through so canary warnings reach the user.
set +e
echo "${INPUT}" | PYTHONPATH="${PROJECT_ROOT}" python3 -m spellbook_mcp.security.check --mode canary
CHECK_EXIT=$?
set -e

debug "check.py exited with code ${CHECK_EXIT}"

if [[ ${CHECK_EXIT} -ne 0 ]]; then
    debug "check.py failed (exit ${CHECK_EXIT}), continuing anyway (fail-open)"
    warn_and_continue "canary check failed"
fi

debug "Canary check completed"
exit 0
