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
    mcpFallbackCheck(input{"tool_input"}, "spawn_claude_session", "spawn_guard")
  else:
    debugLog("spawn_guard", "hash OK, using embedded patterns")
    let findings = checkPatterns(prompt, SPAWN_CHECK_PATTERNS, "standard")
    if findings.len > 0:
      let reasons = findings.mapIt(it.message).join("; ")
      failClosed("Security check failed: " & reasons)

  quit(0)

main()
