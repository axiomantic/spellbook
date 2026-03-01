## state_sanitize - PreToolUse hook for workflow_state_save.
##
## Phase: PreToolUse, matcher: mcp__spellbook__workflow_state_save
## Timeout: 15s
## Failure policy: FAIL-CLOSED
##
## CRITICAL: Unlike bash_gate (single command string) and spawn_guard
## (single prompt string), this hook must RECURSIVELY extract ALL string
## values from the arbitrarily nested tool_input JSON and check each
## one for injection patterns.

import std/[json, os, strutils, sequtils]
import hooklib, generated_patterns

proc main() =
  let input = readStdinJson()
  if input.isNil: failClosed("Security check failed: no input received")

  let toolInput = input{"tool_input"}
  if toolInput.isNil: quit(0)

  debugLog("state_sanitize", "checking workflow state")

  # Verify pattern freshness via hash
  let spellbookDir = resolveSpellbookDir()
  let rulesPath = spellbookDir / "spellbook_mcp" / "security" / "rules.py"

  if not verifyPatternsHash(rulesPath, RULES_PY_HASH):
    mcpFallbackCheck(toolInput, "workflow_state_save", "state_sanitize")
  else:
    debugLog("state_sanitize", "hash OK, using embedded patterns")
    # Recursively extract all string values from the nested tool_input
    let allStrings = extractStrings(toolInput)
    debugLog("state_sanitize", "extracted " & $allStrings.len & " strings")
    for text in allStrings:
      let findings = checkPatterns(text, STATE_CHECK_PATTERNS, "standard")
      if findings.len > 0:
        let reasons = findings.mapIt(it.message).join("; ")
        failClosed("Security check failed: " & reasons)

  quit(0)

main()
