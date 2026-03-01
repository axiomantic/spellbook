## audit_log - PostToolUse hook for audit logging.
##
## Phase: PostToolUse, matcher: Bash|Read|WebFetch|Grep|mcp__.*
## Timeout: 10s, async
## Failure policy: FAIL-OPEN
##
## Calls MCP server to log tool usage to security_events table.
## Never blocks tool execution.
##
## NOTE: The source field is "audit-log.nim" to distinguish from the
## shell version which uses "audit-log.sh". Both are intentional and
## can be used to track which hook implementation recorded an event.

import std/[json, os, strutils]
import hooklib

const AUDIT_DETAIL_MAX_LEN = 500

proc main() =
  let input = readStdinJson()
  if input.isNil: failOpen("no input received")

  let toolName = input.getOrDefault("tool_name").getStr("")
  if toolName.len == 0: failOpen("no tool_name in input")

  let toolInput = input{"tool_input"}
  var detail = ""
  if not toolInput.isNil:
    detail = $toolInput
    if detail.len > AUDIT_DETAIL_MAX_LEN:
      detail = detail[0..<AUDIT_DETAIL_MAX_LEN]

  debugLog("audit_log", "logging " & toolName)

  let host = getEnvOr("SPELLBOOK_MCP_HOST", "127.0.0.1")
  let port = parseInt(getEnvOr("SPELLBOOK_MCP_PORT", "8765"))

  let result = mcpCall(host, port, "security_log_event",
    %*{
      "event_type": "tool_call",
      "severity": "INFO",
      "source": "audit-log.nim",
      "tool_name": toolName,
      "detail": detail,
    })

  if result.isNil:
    debugLog("audit_log", "MCP call failed, continuing (fail-open)")

  quit(0)

main()
