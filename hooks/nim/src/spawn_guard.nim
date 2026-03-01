## spawn_guard - PreToolUse hook for spawn_claude_session.
##
## Phase: PreToolUse, matcher: spawn_claude_session
## Failure policy: FAIL-CLOSED
##
## Checks spawn prompts against embedded injection and escalation patterns.
## Normalizes MCP-prefixed tool_name before checking.

import std/[json, os, strutils, sequtils]
import hooklib, generated_patterns

proc main() =
  let input = readStdinJson()
  if input.isNil: failClosed("Security check failed: no input received")

  let prompt = input{"tool_input", "prompt"}.getStr("")
  if prompt.len == 0: quit(0)

  debugLog("spawn_guard", "checking prompt (" & $prompt.len & " bytes)")

  # Verify pattern freshness via hash
  let spellbookDir = resolveSpellbookDir()
  let rulesPath = spellbookDir / "spellbook_mcp" / "security" / "rules.py"

  if not verifyPatternsHash(rulesPath, RULES_PY_HASH):
    debugLog("spawn_guard", "hash mismatch, falling back to MCP")
    let host = getEnvOr("SPELLBOOK_MCP_HOST", "127.0.0.1")
    let port = parseInt(getEnvOr("SPELLBOOK_MCP_PORT", "8765"))
    # Normalize tool_name for check.py routing
    let mcpResult = mcpCall(host, port, "security_check_tool_input",
      %*{"tool_name": "spawn_claude_session", "tool_input": input{"tool_input"}})
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
    debugLog("spawn_guard", "hash OK, using embedded patterns")
    let findings = checkPatterns(prompt, SPAWN_CHECK_PATTERNS, "standard")
    if findings.len > 0:
      let reasons = findings.mapIt(it.message).join("; ")
      failClosed("Security check failed: " & reasons)

  quit(0)

main()
