## tts_notify - PostToolUse hook for TTS notifications.
##
## Phase: PostToolUse (catch-all, no matcher)
## Timeout: 15s, async
## Failure policy: FAIL-OPEN
##
## Sends POST to MCP server's /api/speak endpoint when a tool
## execution exceeds the configured threshold (default 30s).
## This hook benefits most from Nim: the shell version makes
## 3 separate python3 invocations; Nim does it all natively.

import std/[json, os, strutils, options]
import hooklib

const BLACKLIST = ["AskUserQuestion", "TodoRead", "TodoWrite",
                   "TaskCreate", "TaskUpdate", "TaskGet", "TaskList"]

proc main() =
  let input = readStdinJson()
  if input.isNil: quit(0)

  let toolName = input.getOrDefault("tool_name").getStr("")
  let toolUseId = input.getOrDefault("tool_use_id").getStr("")
  let cwd = input.getOrDefault("cwd").getStr("")

  # Check blacklist
  if toolName in BLACKLIST: quit(0)

  # Validate tool_use_id
  if toolUseId.len == 0: quit(0)
  let sanitized = sanitizeToolUseId(toolUseId)
  if sanitized.isNone: quit(0)

  # Read start timestamp
  let startFile = "/tmp/claude-tool-start-" & sanitized.get
  if not fileExists(startFile): quit(0)

  var startTs: int64
  try:
    let content = readFile(startFile).strip()
    startTs = parseBiggestInt(content)
  except ValueError, IOError:
    quit(0)

  # Delete start file
  try:
    removeFile(startFile)
  except OSError:
    discard

  # Check threshold
  let threshold = parseInt(getEnvOr("SPELLBOOK_TTS_THRESHOLD", "30"))
  let now = unixTimestamp()
  let elapsed = now - startTs
  if elapsed < threshold: quit(0)

  # Build announcement message
  let project = if cwd.len > 0: cwd.lastPathPart else: "unknown"

  var detail = ""
  let toolInput = input{"tool_input"}
  if toolName == "Bash" and not toolInput.isNil:
    let cmd = toolInput.getOrDefault("command").getStr("")
    if cmd.len > 0:
      let tokens = shellTokenize(cmd)
      if tokens.len > 0:
        detail = tokens[0].lastPathPart  # Strip path prefix
  elif toolName == "Task" and not toolInput.isNil:
    detail = toolInput.getOrDefault("description").getStr("")
    if detail.len > 40:
      detail = detail[0..<40]

  var parts = @[project, toolName]
  if detail.len > 0:
    parts.add(detail)
  parts.add("finished")
  let message = parts.join(" ")

  if message.len == 0: quit(0)

  # Send to MCP server
  let host = getEnvOr("SPELLBOOK_MCP_HOST", "127.0.0.1")
  let port = parseInt(getEnvOr("SPELLBOOK_MCP_PORT", "8765"))
  speakVia(host, port, message)

  quit(0)

main()
