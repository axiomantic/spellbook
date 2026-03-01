## tts_timer_start - PreToolUse hook for recording tool start times.
##
## Phase: PreToolUse (catch-all, no matcher)
## Timeout: 5s, async
## Failure policy: FAIL-OPEN (timing failures never prevent tool execution)
##
## Writes current Unix timestamp to /tmp/claude-tool-start-{tool_use_id}.
## The companion tts_notify PostToolUse hook reads and deletes this file.

import std/[json, os, strutils, options]
import hooklib

proc main() =
  let input = readStdinJson()
  if input.isNil: quit(0)

  let toolUseId = input.getOrDefault("tool_use_id").getStr("")

  if toolUseId.len > 0:
    let sanitized = sanitizeToolUseId(toolUseId)
    if sanitized != none(string):
      let ts = $unixTimestamp()
      let path = "/tmp/claude-tool-start-" & sanitized.get
      try:
        writeFile(path, ts & "\n")
      except IOError:
        discard  # fail-open

  quit(0)

main()
