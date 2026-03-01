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
    mcpFallbackCheck(input{"tool_input"}, "Bash", "bash_gate")
  else:
    debugLog("bash_gate", "hash OK, using embedded patterns")
    # Patterns fresh: use embedded patterns
    let findings = checkPatterns(command, BASH_CHECK_PATTERNS, "standard")
    if findings.len > 0:
      let reasons = findings.mapIt(it.message).join("; ")
      failClosed("Security check failed: " & reasons)

  quit(0)

main()
