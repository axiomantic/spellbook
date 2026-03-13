#!/usr/bin/env bash
# memory-capture.sh - PostToolUse hook for memory event capture
#
# Claude Code Hook Protocol (PostToolUse):
#   Receives JSON on stdin: {"tool_name":"...","tool_input":{...},
#     "tool_use_id":"...","session_id":"...","cwd":"..."}
#   Exit 0: always (capture hook, never blocks)
#
# FAILURE POLICY: FAIL-OPEN
#   Memory capture failures must NEVER prevent tool execution.
#
# POSTs raw events to MCP server's /api/memory/event endpoint.
# Falls back silently if MCP server not running.

set -euo pipefail

# Fail-open: if python3 is not available, skip silently
command -v python3 >/dev/null 2>&1 || exit 0

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MCP_PORT="${SPELLBOOK_MCP_PORT:-8765}"
MCP_HOST="${SPELLBOOK_MCP_HOST:-127.0.0.1}"
EVENT_URL="http://${MCP_HOST}:${MCP_PORT}/api/memory/event"
TOKEN_FILE="${HOME}/.local/spellbook/.mcp-token"
AUTH_HEADER=""
if [[ -f "${TOKEN_FILE}" ]]; then
    AUTH_HEADER="Authorization: Bearer $(cat "${TOKEN_FILE}")"
fi

# ---------------------------------------------------------------------------
# Tool blacklist: tools that should NOT be captured
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
# Extract fields and build payload with lightweight JSON parsing
# ---------------------------------------------------------------------------
PAYLOAD=$(echo "${INPUT}" | python3 -c "
import json, os, sys

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool_name = d.get('tool_name', '')
if not tool_name:
    sys.exit(0)

# Check blacklist
blacklist = set('${BLACKLIST}'.split('|'))
if tool_name in blacklist:
    sys.exit(0)

tool_input = d.get('tool_input') or {}
session_id = d.get('session_id', '')
cwd = d.get('cwd', '')

# Extract subject (file path) from tool input
subject = ''
if tool_name in ('Read', 'Write', 'Edit'):
    subject = tool_input.get('file_path', '')
elif tool_name == 'Bash':
    subject = (tool_input.get('command', '') or '')[:200]
elif tool_name in ('Grep', 'Glob'):
    subject = tool_input.get('pattern', '')
elif tool_name == 'WebFetch':
    subject = tool_input.get('url', '')
else:
    # For MCP tools, use the tool name as subject
    subject = tool_name

# Build summary
summary = f'{tool_name}'
if subject:
    summary += f': {subject[:100]}'
desc = tool_input.get('description', '')
if desc:
    summary += f' ({desc[:80]})'

# Resolve worktree to repo root for consistent namespace
import subprocess as _sp2
_resolved_cwd = cwd
try:
    _wt_result = _sp2.run(
        ['git', 'worktree', 'list', '--porcelain'],
        cwd=cwd, capture_output=True, text=True, timeout=3,
    )
    if _wt_result.returncode == 0 and _wt_result.stdout.strip():
        _first_line = _wt_result.stdout.strip().split('\n')[0]
        if _first_line.startswith('worktree '):
            _resolved_cwd = _first_line[len('worktree '):]
except Exception:
    pass

# Project namespace (project-encoded)
namespace = _resolved_cwd.replace('/', '-').lstrip('-') if _resolved_cwd else 'unknown'

# Build tags
tags_list = [tool_name.lower()]
if subject:
    # Extract filename from path (handle both / and \ separators)
    normalized = subject.replace('\\\\', '/')
    parts = normalized.rsplit('/', 1)
    if len(parts) > 1:
        tags_list.append(parts[-1].lower())

# Detect git branch
import subprocess as _sp
try:
    _branch = _sp.run(
        ['git', '-C', cwd, 'rev-parse', '--abbrev-ref', 'HEAD'],
        capture_output=True, text=True, timeout=2
    ).stdout.strip() if cwd else ''
except Exception:
    _branch = ''

payload = {
    'session_id': session_id,
    'project': namespace,
    'tool_name': tool_name,
    'subject': subject,
    'summary': summary[:500],
    'tags': ','.join(tags_list),
    'event_type': 'tool_use',
    'branch': _branch,
}
print(json.dumps(payload))
" 2>/dev/null) || exit 0

if [[ -z "${PAYLOAD}" ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Debug mode: print payload to stdout for testing
# ---------------------------------------------------------------------------
if [[ "${DEBUG_PAYLOAD:-}" == "1" ]]; then
    echo "${PAYLOAD}"
    exit 0
fi

# ---------------------------------------------------------------------------
# POST to MCP server (fail silently)
# ---------------------------------------------------------------------------
curl -s -m 5 -X POST "${EVENT_URL}" \
    -H "Content-Type: application/json" \
    ${AUTH_HEADER:+-H "${AUTH_HEADER}"} \
    -d "${PAYLOAD}" \
    >/dev/null 2>&1 || true

exit 0
