## canary_check - PostToolUse hook for canary token detection.
##
## Phase: PostToolUse, matcher: Bash|Read|WebFetch|Grep|mcp__.*
## Timeout: 10s
## Failure policy: FAIL-OPEN
##
## Calls MCP server to check tool output for registered canary tokens.
## Canary tokens are user-created at runtime (stored in SQLite), so
## they CANNOT be embedded at compile time. MCP call is mandatory.

import std/[json, os, strutils]
import hooklib

proc main() =
  let input = readStdinJson()
  if input.isNil: failOpen("no input received")

  # canary_check receives tool_output (note: different from other hooks)
  let toolOutput = input.getOrDefault("tool_output").getStr("")
  if toolOutput.len == 0:
    debugLog("canary_check", "no tool_output, skipping")
    quit(0)

  debugLog("canary_check", "checking output (" & $toolOutput.len & " bytes)")

  let host = getEnvOr("SPELLBOOK_MCP_HOST", "127.0.0.1")
  let port = parseInt(getEnvOr("SPELLBOOK_MCP_PORT", "8765"))

  let result = mcpCall(host, port, "security_canary_check",
    %*{"content": toolOutput})

  if result.isNil:
    debugLog("canary_check", "MCP call failed, continuing (fail-open)")
  else:
    # security_canary_check returns {"clean": bool, "triggered_canaries": [...]}
    # clean=true means no canaries found; clean=false means triggered
    let triggered = not result.getOrDefault("clean").getBool(true)
    if triggered:
      # Iterate triggered_canaries for details
      let canaries = result.getOrDefault("triggered_canaries")
      var details: seq[string]
      if not canaries.isNil and canaries.kind == JArray:
        for canary in canaries.items:
          let token = canary.getOrDefault("token").getStr("")
          let tokenType = canary.getOrDefault("token_type").getStr("")
          if token.len > 0:
            details.add(tokenType & ":" & token)
      let warning = if details.len > 0:
        "Canary token(s) detected in tool output: " & details.join(", ")
      else:
        "Canary token detected in tool output"
      stderr.writeLine("[canary-check] WARNING: " & warning)

  quit(0)

main()
