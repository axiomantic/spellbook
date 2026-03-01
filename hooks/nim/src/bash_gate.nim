## bash_gate - PreToolUse hook for the Bash tool.
##
## Phase: PreToolUse, matcher: Bash
## Failure policy: FAIL-CLOSED (unknown errors block tool execution)
##
## Checks bash commands against embedded security patterns.
## Falls back to MCP JSON-RPC if patterns are stale (hash mismatch).

import std/[json, os, strutils, sequtils]
import hooklib, generated_patterns

proc main() =
  let input = readStdinJson()
  if input.isNil: failClosed("Security check failed: no input received")

  let command = input{"tool_input", "command"}.getStr("")
  if command.len == 0: quit(0)  # No command to check

  debugLog("bash_gate", "checking command (" & $command.len & " bytes)")

  # Verify pattern freshness via hash
  let spellbookDir = resolveSpellbookDir()
  let rulesPath = spellbookDir / "spellbook_mcp" / "security" / "rules.py"

  if not verifyPatternsHash(rulesPath, RULES_PY_HASH):
    debugLog("bash_gate", "hash mismatch, falling back to MCP")
    # Patterns stale: fall back to MCP call
    let host = getEnvOr("SPELLBOOK_MCP_HOST", "127.0.0.1")
    let port = parseInt(getEnvOr("SPELLBOOK_MCP_PORT", "8765"))
    # Build the full input as check.py expects it
    let mcpResult = mcpCall(host, port, "security_check_tool_input",
      %*{"tool_name": "Bash", "tool_input": input{"tool_input"}})
    if mcpResult.isNil:
      failClosed("Security check failed: stale patterns and MCP unavailable")
    let safe = mcpResult.getOrDefault("safe").getBool(true)
    if not safe:
      let findings = mcpResult.getOrDefault("findings")
      var reason = "Security check failed: blocked by MCP"
      if not findings.isNil and findings.kind == JArray and findings.len > 0:
        reason = "Security check failed: " & findings[0].getOrDefault("message").getStr("blocked")
      failClosed(reason)
  else:
    debugLog("bash_gate", "hash OK, using embedded patterns")
    # Patterns fresh: use embedded patterns
    let findings = checkPatterns(command, BASH_CHECK_PATTERNS, "standard")
    if findings.len > 0:
      let reasons = findings.mapIt(it.message).join("; ")
      failClosed("Security check failed: " & reasons)

  quit(0)

main()
