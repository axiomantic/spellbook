## post_compact_recover - SessionStart hook for post-compaction recovery.
##
## Phase: SessionStart (catch-all, no matcher)
## Timeout: 10s
## Failure policy: FAIL-OPEN (outputs fallback directive on any error)
##
## This is the most complex hook. The shell version makes 10+ python3
## subprocess invocations. The Nim version eliminates all of them.

import std/[json, os, strutils]
import hooklib

const LOG_FILE_SUFFIX = "/.local/spellbook/logs/post-compact-recover.log"

proc main() =
  let logFile = getHomeDir() & LOG_FILE_SUFFIX

  let input = readStdinJson()
  if input.isNil:
    logToFile(logFile, "Empty stdin, outputting fallback")
    outputFallbackDirective()

  let projectPath = input.getOrDefault("cwd").getStr("")
  let source = input.getOrDefault("source").getStr("")

  if projectPath.len == 0:
    logToFile(logFile, "No cwd in stdin JSON")
    outputFallbackDirective()

  # Safety check: only proceed if source is "compact"
  if source != "compact":
    logToFile(logFile, "Source is '" & source & "', not 'compact' - exiting without directive")
    quit(0)

  logToFile(logFile, "Post-compaction recovery for: " & projectPath)

  let host = getEnvOr("SPELLBOOK_MCP_HOST", "127.0.0.1")
  let port = parseInt(getEnvOr("SPELLBOOK_MCP_PORT", "8765"))

  # Step 1: Load workflow state
  logToFile(logFile, "Loading workflow state")
  let loadResult = mcpCall(host, port, "workflow_state_load",
    %*{"project_path": projectPath, "max_age_hours": 24})

  if loadResult.isNil:
    logToFile(logFile, "MCP daemon unreachable, outputting fallback directive")
    outputFallbackDirective()

  let found = loadResult.getOrDefault("found").getBool(false)
  if not found:
    logToFile(logFile, "No workflow state found, outputting minimal directive")
    outputFallbackDirective()

  # Step 2: Extract state details
  let state = loadResult.getOrDefault("state")
  if state.isNil:
    logToFile(logFile, "No state object in load result")
    outputFallbackDirective()

  let activeSkill = state.getOrDefault("active_skill").getStr("")
  let skillPhase = state.getOrDefault("skill_phase").getStr("")
  let workflowPattern = state.getOrDefault("workflow_pattern").getStr("")
  let nextAction = state.getOrDefault("next_action").getStr("")
  let bindingDecisions = state.getOrDefault("binding_decisions")

  # Step 3: Fetch skill constraints if active skill exists
  var skillConstraints = ""
  if activeSkill.len > 0:
    logToFile(logFile, "Fetching skill constraints for: " & activeSkill)
    let skillResult = mcpCall(host, port, "skill_instructions_get",
      %*{"skill_name": activeSkill, "sections": ["FORBIDDEN", "REQUIRED"]})

    if not skillResult.isNil:
      let success = skillResult.getOrDefault("success").getBool(false)
      if success:
        let sections = skillResult.getOrDefault("sections")
        if not sections.isNil:
          var parts: seq[string]
          let forbidden = sections.getOrDefault("FORBIDDEN").getStr("")
          let required = sections.getOrDefault("REQUIRED").getStr("")
          if forbidden.len > 0:
            parts.add("**FORBIDDEN:**\n" & forbidden)
          if required.len > 0:
            parts.add("**REQUIRED:**\n" & required)
          skillConstraints = parts.join("\n\n")

  # Step 4: Build recovery directive
  logToFile(logFile, "Building recovery directive")

  var parts: seq[string]
  parts.add("## POST-COMPACTION RECOVERY DIRECTIVE")
  parts.add("")
  parts.add("**CRITICAL**: Context was just compacted. You MUST take these actions IMMEDIATELY, before ANY other work:")
  parts.add("")
  parts.add("1. Call `spellbook_session_init` MCP tool")
  parts.add("2. Execute the returned `resume_boot_prompt` completely")
  parts.add("3. Do NOT implement code directly - you are an ORCHESTRATOR")
  parts.add("")

  if activeSkill.len > 0 or skillPhase.len > 0:
    parts.add("### Active Workflow")
    if activeSkill.len > 0:
      parts.add("- **Skill**: " & activeSkill)
    if skillPhase.len > 0:
      parts.add("- **Phase**: " & skillPhase)
    if workflowPattern.len > 0:
      parts.add("- **Pattern**: " & workflowPattern)
    parts.add("")

  if skillConstraints.len > 0:
    parts.add("### Skill Constraints")
    parts.add(skillConstraints)
    parts.add("")

  if not bindingDecisions.isNil and bindingDecisions.kind == JArray and bindingDecisions.len > 0:
    parts.add("### Binding Decisions (DO NOT REVISIT)")
    for decision in bindingDecisions.items:
      if decision.kind == JString:
        parts.add("- " & decision.getStr())
      elif decision.kind == JObject:
        let desc = decision.getOrDefault("description").getStr(
          decision.getOrDefault("decision").getStr($decision))
        parts.add("- " & desc)
    parts.add("")

  if nextAction.len > 0:
    parts.add("### Next Action")
    parts.add(nextAction)
    parts.add("")

  let directive = parts.join("\n")

  if directive.len == 0:
    logToFile(logFile, "Empty directive, using fallback")
    outputFallbackDirective()

  # Step 5: Output as hookSpecificOutput JSON
  let output = %*{
    "hookSpecificOutput": {
      "hookEventName": "SessionStart",
      "additionalContext": directive,
    }
  }
  stdout.writeLine($output)

  logToFile(logFile, "Recovery directive output successfully")
  quit(0)

main()
