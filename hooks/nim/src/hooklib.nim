## hooklib - Shared library module for all compiled hooks.
##
## Provides common functions for:
##   - Stdin JSON reading
##   - Recursive string extraction from nested JSON
##   - Environment variable access with defaults
##   - Spellbook directory resolution
##   - Tool use ID sanitization
##   - Error handling (fail-open, fail-closed)
##   - MCP HTTP JSON-RPC calls with SSE response parsing
##   - TTS speak endpoint calls
##   - File logging with directory creation
##   - Shell command tokenization
##   - MCP tool name normalization
##   - Debug logging

import std/[json, os, options, strutils, times, httpclient, net, sha1]

# =============================================================================
# Stdin / JSON
# =============================================================================

proc readStdinJson*(): JsonNode =
  ## Read all stdin and parse as JSON.
  ## Returns nil on empty stdin or parse failure.
  let raw = stdin.readAll()
  if raw.len == 0:
    return nil
  try:
    return parseJson(raw)
  except JsonParsingError:
    return nil

proc extractStrings*(node: JsonNode): seq[string] =
  ## Recursively walk nested JSON, collecting all string leaf values.
  ## Used by state_sanitize for scanning arbitrarily nested workflow state.
  case node.kind
  of JString:
    result.add(node.getStr())
  of JObject:
    for key, value in node.pairs:
      result.add(extractStrings(value))
  of JArray:
    for item in node.items:
      result.add(extractStrings(item))
  of JInt, JFloat, JBool, JNull:
    discard

# =============================================================================
# Environment / Config
# =============================================================================

proc getEnvOr*(key: string, default: string): string =
  ## Get environment variable with default value.
  let val = getEnv(key)
  if val.len == 0: default else: val

proc resolveSpellbookDir*(): string =
  ## Resolve $SPELLBOOK_DIR or derive from binary location.
  ## Binary is at hooks/nim/bin/<name>, project root is 3 levels up.
  let envDir = getEnv("SPELLBOOK_DIR")
  if envDir.len > 0:
    return envDir
  let binDir = getAppDir()
  return binDir.parentDir.parentDir.parentDir

proc sanitizeToolUseId*(id: string): Option[string] =
  ## Validate tool_use_id against path traversal.
  ## Rejects '/', whitespace, '..' patterns.
  if id.len == 0: return none(string)
  for c in id:
    if c == '/' or c.isSpaceAscii:
      return none(string)
  if ".." in id:
    return none(string)
  return some(id)

# =============================================================================
# Error Handling
# =============================================================================

proc failOpen*(msg: string) =
  ## Log warning to stderr and exit 0.
  ## Used by fail-open hooks (tts-*, audit-log, canary-check, compaction hooks).
  stderr.writeLine("[hooklib] WARNING: " & msg)
  quit(0)

proc failClosed*(reason: string) =
  ## Output JSON error to stdout and exit 2.
  ## Used by fail-closed security hooks (bash-gate, spawn-guard, state-sanitize).
  let errorJson = %*{"error": reason}
  stdout.writeLine($errorJson)
  quit(2)

proc outputFallbackDirective*() =
  ## Output minimal fallback recovery directive and exit 0.
  ## Used by post_compact_recover on any error.
  let output = %*{
    "hookSpecificOutput": {
      "hookEventName": "SessionStart",
      "additionalContext": "COMPACTION OCCURRED. Call spellbook_session_init to restore workflow state."
    }
  }
  stdout.writeLine($output)
  quit(0)

# =============================================================================
# Debug Logging
# =============================================================================

proc debugLog*(prefix, msg: string) =
  ## Write debug message to stderr if debug logging is enabled.
  ## Checks both SPELLBOOK_DEBUG and SPELLBOOK_SECURITY_DEBUG env vars.
  let debugEnv = getEnv("SPELLBOOK_DEBUG")
  let secDebugEnv = getEnv("SPELLBOOK_SECURITY_DEBUG")
  if debugEnv.len > 0 or secDebugEnv.len > 0:
    stderr.writeLine("[" & prefix & "] " & msg)

# =============================================================================
# HTTP / MCP
# =============================================================================

proc parseSseResponse*(rawBody: string): JsonNode =
  ## Parse multi-layer SSE response from MCP server.
  ##
  ## Extraction layers:
  ##   1. Split on newlines, find lines starting with "data: "
  ##   2. Parse data payload as JSON
  ##   3. Look for "result" key in JSON-RPC response
  ##   4. Check for structuredContent (preferred)
  ##   5. Fall back to content array, find type=="text" items
  ##   6. Parse double-encoded JSON from text field
  for line in rawBody.splitLines():
    let trimmed = line.strip()
    if not trimmed.startsWith("data: "):
      continue

    let payload = trimmed[6..^1]  # Strip "data: " prefix
    var parsed: JsonNode
    try:
      parsed = parseJson(payload)
    except JsonParsingError:
      debugLog("hooklib", "SSE: failed to parse data line as JSON")
      continue

    let resultNode = parsed.getOrDefault("result")
    if resultNode.isNil:
      continue

    # Layer 4: Check structuredContent first
    let sc = resultNode.getOrDefault("structuredContent")
    if not sc.isNil:
      return sc

    # Layer 5: Fall back to content array
    let content = resultNode.getOrDefault("content")
    if not content.isNil and content.kind == JArray:
      for item in content.items:
        if item.getOrDefault("type").getStr("") == "text":
          let textStr = item.getOrDefault("text").getStr("")
          if textStr.len > 0:
            # Layer 6: Double-encoded JSON
            try:
              return parseJson(textStr)
            except JsonParsingError:
              debugLog("hooklib", "SSE: failed to parse double-encoded text JSON")
              continue

  return nil  # No valid result found

proc mcpCall*(
  host: string,
  port: int,
  toolName: string,
  arguments: JsonNode,
  connectTimeout: int = 500,   # milliseconds (used as total timeout floor)
  totalTimeout: int = 2000,    # milliseconds
): JsonNode =
  ## Call an MCP tool via HTTP JSON-RPC and parse the SSE response.
  ## Returns the tool result JsonNode, or nil on failure.
  ##
  ## NOTE: Nim's std/httpclient does not expose a separate connectTimeout
  ## parameter. The `connectTimeout` arg here is accepted for API compatibility
  ## with the design doc but the actual socket-level timeout is controlled
  ## solely by `totalTimeout`. If fine-grained connect vs read timeouts are
  ## needed in the future, switch to nim-chronos HttpClient.
  let url = "http://" & host & ":" & $port & "/mcp"
  let body = %*{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": toolName,
      "arguments": arguments,
    }
  }

  var client = newHttpClient(
    timeout = totalTimeout,
  )
  client.headers = newHttpHeaders({
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
  })

  try:
    let response = client.postContent(url, $body)
    return parseSseResponse(response)
  except HttpRequestError, TimeoutError, OSError, IOError, ValueError:
    debugLog("hooklib", "MCP call to " & toolName & " failed: " & getCurrentExceptionMsg())
    return nil
  finally:
    client.close()

proc speakVia*(host: string, port: int, text: string,
               connectTimeout: int = 500, totalTimeout: int = 2000) =
  ## POST to /api/speak endpoint for TTS notification.
  ## NOTE: connectTimeout accepted for API compat but not separately applied;
  ## see mcpCall note about Nim std/httpclient limitations.
  let url = "http://" & host & ":" & $port & "/api/speak"
  let body = %*{"text": text}

  var client = newHttpClient(
    timeout = totalTimeout,
  )
  client.headers = newHttpHeaders({"Content-Type": "application/json"})

  try:
    discard client.postContent(url, $body)
  except HttpRequestError, TimeoutError, OSError, IOError, ValueError:
    discard  # fail-open
  finally:
    client.close()

# =============================================================================
# File I/O
# =============================================================================

proc logToFile*(path: string, msg: string) =
  ## Append a timestamped log line to a file.
  ## Creates parent directory if it does not exist.
  ## Silently ignores all errors (logs must never cause failures).
  try:
    let dir = path.parentDir
    createDir(dir)
    let f = open(path, fmAppend)
    defer: f.close()
    let ts = now().format("yyyy-MM-dd HH:mm:ss")
    f.writeLine("[" & ts & "] " & msg)
  except IOError, OSError:
    discard

proc unixTimestamp*(): int64 =
  ## Return current Unix timestamp as int64.
  return epochTime().int64

# =============================================================================
# String Utilities
# =============================================================================

proc shellTokenize*(cmd: string): seq[string] =
  ## Minimal shlex-equivalent tokenizer for extracting command words.
  ##
  ## Handles:
  ##   - Unquoted words (split on whitespace)
  ##   - Single-quoted strings (no escapes, literal)
  ##   - Double-quoted strings (backslash-escape for " and \)
  ##
  ## Used by tts_notify to extract the first command word for display.
  var tokens: seq[string]
  var current = ""
  var i = 0
  var inSingle = false
  var inDouble = false

  while i < cmd.len:
    let c = cmd[i]

    if inSingle:
      if c == '\'':
        inSingle = false
      else:
        current.add(c)
    elif inDouble:
      if c == '\\' and i + 1 < cmd.len and cmd[i + 1] in {'"', '\\'}:
        current.add(cmd[i + 1])
        inc i
      elif c == '"':
        inDouble = false
      else:
        current.add(c)
    elif c == '\'':
      inSingle = true
    elif c == '"':
      inDouble = true
    elif c.isSpaceAscii:
      if current.len > 0:
        tokens.add(current)
        current = ""
    else:
      current.add(c)

    inc i

  if current.len > 0:
    tokens.add(current)

  return tokens

proc normalizeMcpToolName*(name: string): string =
  ## Strip MCP prefix from tool name.
  ## "mcp__spellbook__spawn_claude_session" -> "spawn_claude_session"
  ## "Bash" -> "Bash" (unchanged)
  let parts = name.split("__")
  if parts.len >= 3 and parts[0] == "mcp":
    return parts[^1]  # Last segment
  return name

# =============================================================================
# Hash Verification
# =============================================================================

proc verifyPatternsHash*(rulesPath: string, expectedHash: string): bool =
  ## Returns true if rules.py matches the expected hash.
  ## Returns false if file is missing, unreadable, or hash mismatches.
  try:
    let content = readFile(rulesPath)
    let currentHash = "sha1:" & $secureHash(content)
    return currentHash == expectedHash
  except IOError:
    return false
