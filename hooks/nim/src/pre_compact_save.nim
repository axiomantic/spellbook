## pre_compact_save - PreCompact hook to save workflow state before compaction.
##
## Phase: PreCompact (catch-all, no matcher)
## Timeout: 5s
## Failure policy: FAIL-OPEN (must never block compaction)
##
## Flow:
##   1. Read stdin JSON, extract cwd as project path
##   2. Call workflow_state_load via MCP HTTP
##   3. Check if state is fresh (< 5 minutes)
##   4. If stale, save with compaction_flag and trigger="auto"

import std/[json, os, strutils]
import hooklib

const LOG_FILE_SUFFIX = "/.local/spellbook/logs/pre-compact.log"
const FRESHNESS_THRESHOLD = 0.083  # 5 minutes in hours

proc main() =
  let logFile = getHomeDir() & LOG_FILE_SUFFIX

  let input = readStdinJson()
  if input.isNil:
    logToFile(logFile, "Empty stdin, exiting")
    quit(0)

  let projectPath = input.getOrDefault("cwd").getStr("")
  if projectPath.len == 0:
    logToFile(logFile, "No cwd in stdin JSON, exiting")
    quit(0)

  logToFile(logFile, "Project path: " & projectPath)

  let host = getEnvOr("SPELLBOOK_MCP_HOST", "127.0.0.1")
  let port = parseInt(getEnvOr("SPELLBOOK_MCP_PORT", "8765"))

  # Step 1: Load current workflow state
  logToFile(logFile, "Checking for existing workflow state")
  let loadResult = mcpCall(host, port, "workflow_state_load",
    %*{"project_path": projectPath, "max_age_hours": 24},
    connectTimeout = 500, totalTimeout = 1500)

  if loadResult.isNil:
    logToFile(logFile, "MCP daemon unreachable or workflow_state_load failed, exiting")
    quit(0)

  # Step 2: Check freshness
  let found = loadResult.getOrDefault("found").getBool(false)
  let ageHours = loadResult.getOrDefault("age_hours").getFloat(-1.0)

  if found and ageHours >= 0.0 and ageHours < FRESHNESS_THRESHOLD:
    logToFile(logFile, "Workflow state is fresh (< 5 min old), nothing to do")
    quit(0)

  # Step 3: Save state with compaction flag
  logToFile(logFile, "Saving workflow state (trigger=auto)")

  var existingState = newJObject()
  let stateNode = loadResult.getOrDefault("state")
  if not stateNode.isNil and stateNode.kind == JObject:
    existingState = stateNode.copy()

  if not existingState.hasKey("compaction_flag"):
    existingState["compaction_flag"] = %true

  let saveArgs = %*{
    "project_path": projectPath,
    "state": existingState,
    "trigger": "auto",
  }

  let saveResult = mcpCall(host, port, "workflow_state_save", saveArgs,
    connectTimeout = 500, totalTimeout = 1500)

  if saveResult.isNil:
    logToFile(logFile, "workflow_state_save failed")
  else:
    logToFile(logFile, "Save result: " & $saveResult)

  logToFile(logFile, "Pre-compact save complete")
  quit(0)

main()
