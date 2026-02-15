#!/usr/bin/env bash
# audit-log.sh - PostToolUse hook for audit logging
#
# Claude Code Hook Protocol (PostToolUse):
#   Receives JSON on stdin: {"tool_name": "...", "tool_input": {...}}
#   Exit 0: always (this hook NEVER blocks tool execution)
#
# FAILURE POLICY: FAIL-OPEN
#   Logging failures must NEVER prevent tool execution. All error paths
#   exit 0 with a stderr warning. This is the opposite of fail-closed
#   hooks like bash-gate.sh and spawn-guard.sh.
#
# This hook delegates audit logging to spellbook_mcp.security.check --mode audit,
# which inserts a record into the security_events table.
# Error messages never include input content to prevent reflection attacks.

set -euo pipefail

# ---------------------------------------------------------------------------
# Debug logging (only when SPELLBOOK_DEBUG is set and non-empty)
# ---------------------------------------------------------------------------
debug() {
    if [[ -n "${SPELLBOOK_DEBUG:-}" ]]; then
        echo "[audit-log] $*" >&2
    fi
}

# ---------------------------------------------------------------------------
# Fail-open helper: warn on stderr but always exit 0
# ---------------------------------------------------------------------------
warn_and_continue() {
    local reason="${1:-Audit logging unavailable}"
    echo "[audit-log] WARNING: ${reason}" >&2
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
# Invoke the security check module in audit mode
# ---------------------------------------------------------------------------
debug "Running audit logging"

# Run check.py with --mode audit, capturing exit code.
# PYTHONPATH ensures the module can be imported from the project root.
# Audit mode is fail-open: check.py --mode audit always exits 0.
set +e
echo "${INPUT}" | PYTHONPATH="${PROJECT_ROOT}" python3 -m spellbook_mcp.security.check --mode audit 2>/dev/null
CHECK_EXIT=$?
set -e

debug "check.py exited with code ${CHECK_EXIT}"

if [[ ${CHECK_EXIT} -ne 0 ]]; then
    debug "check.py failed (exit ${CHECK_EXIT}), continuing anyway (fail-open)"
    warn_and_continue "audit logging failed"
fi

debug "Audit logged successfully"
exit 0
