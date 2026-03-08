#!/usr/bin/env bash
# memory-inject.sh - PostToolUse hook for memory injection
#
# Claude Code Hook Protocol (PostToolUse):
#   Receives JSON on stdin: {"tool_name":"...","tool_input":{...},...}
#   Outputs to stdout: injected context (appended after tool result)
#   Exit 0: always (injection hook, never blocks)
#
# FAILURE POLICY: FAIL-OPEN
#   Memory injection failures must NEVER prevent tool execution.
#
# For Read/Edit/Grep/Glob tools, queries MCP server for memories
# related to the file path and outputs them as <spellbook-memory> XML.

set -euo pipefail

# Fail-open: if python3 is not available, skip silently
command -v python3 >/dev/null 2>&1 || exit 0

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MCP_PORT="${SPELLBOOK_MCP_PORT:-8765}"
MCP_HOST="${SPELLBOOK_MCP_HOST:-127.0.0.1}"
RECALL_URL="http://${MCP_HOST}:${MCP_PORT}/api/memory/recall"

# ---------------------------------------------------------------------------
# Read stdin
# ---------------------------------------------------------------------------
INPUT="$(cat)"
if [[ -z "${INPUT}" ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Extract tool info, check eligibility, and build recall payload in one block
# ---------------------------------------------------------------------------
RECALL_PAYLOAD=$(echo "${INPUT}" | python3 -c "
import json, sys

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool_name = d.get('tool_name', '')
tool_input = d.get('tool_input') or {}
cwd = d.get('cwd', '')

# Only process file-related tools
file_tools = {'Read', 'Edit', 'Grep', 'Glob'}
if tool_name not in file_tools:
    sys.exit(0)

# Extract file path
file_path = ''
if tool_name in ('Read', 'Write', 'Edit'):
    file_path = tool_input.get('file_path', '')
elif tool_name == 'Grep':
    file_path = tool_input.get('path', '')
elif tool_name == 'Glob':
    file_path = tool_input.get('path', '')

if not file_path:
    sys.exit(0)

namespace = cwd.replace('/', '-').lstrip('-') if cwd else ''
if not namespace:
    sys.exit(0)

# Build the complete JSON payload for the recall API call.
# Constructing the entire payload in Python avoids fragile inline
# JSON escaping in bash (file paths may contain quotes, spaces, etc).
payload = {'file_path': file_path, 'namespace': namespace, 'limit': 5}
print(json.dumps(payload))
" 2>/dev/null) || exit 0

if [[ -z "${RECALL_PAYLOAD}" ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Query MCP server for memories (fail silently)
# ---------------------------------------------------------------------------
RESPONSE=$(curl -s -m 3 -X POST "${RECALL_URL}" \
    -H "Content-Type: application/json" \
    -d "${RECALL_PAYLOAD}" \
    2>/dev/null) || exit 0

if [[ -z "${RESPONSE}" ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Format memories as XML for injection
# ---------------------------------------------------------------------------
echo "${RESPONSE}" | python3 -c "
import json, sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

memories = data.get('memories', [])
if not memories:
    sys.exit(0)

lines = ['<spellbook-memory>']
for mem in memories[:5]:
    content = mem.get('content', '')
    mtype = mem.get('memory_type', 'fact')
    importance = mem.get('importance', 1.0)
    status = mem.get('status', 'active')
    confidence = 'verified' if status == 'active' else 'unverified'

    lines.append(f'  <memory type=\"{mtype}\" confidence=\"{confidence}\" importance=\"{importance:.1f}\">')
    lines.append(f'    {content}')
    lines.append(f'  </memory>')
lines.append('</spellbook-memory>')
print('\n'.join(lines))
" 2>/dev/null || true

exit 0
