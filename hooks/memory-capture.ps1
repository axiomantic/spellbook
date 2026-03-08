# memory-capture.ps1 - PostToolUse hook for memory event capture (Windows)
#
# FAILURE POLICY: FAIL-OPEN
# Memory capture failures must NEVER prevent tool execution.

$ErrorActionPreference = "SilentlyContinue"

$MCP_PORT = if ($env:SPELLBOOK_MCP_PORT) { $env:SPELLBOOK_MCP_PORT } else { "8765" }
$MCP_HOST = if ($env:SPELLBOOK_MCP_HOST) { $env:SPELLBOOK_MCP_HOST } else { "127.0.0.1" }
$EVENT_URL = "http://${MCP_HOST}:${MCP_PORT}/api/memory/event"

$BLACKLIST = @("AskUserQuestion", "TodoRead", "TodoWrite", "TaskCreate", "TaskUpdate", "TaskGet", "TaskList")

$input_text = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($input_text)) { exit 0 }

try {
    $data = $input_text | ConvertFrom-Json
} catch {
    exit 0
}

$toolName = $data.tool_name
if ([string]::IsNullOrWhiteSpace($toolName)) { exit 0 }
if ($BLACKLIST -contains $toolName) { exit 0 }

$toolInput = $data.tool_input
$sessionId = $data.session_id
$cwd = $data.cwd

$subject = ""
switch ($toolName) {
    { $_ -in @("Read", "Write", "Edit") } { $subject = $toolInput.file_path }
    "Bash" { $subject = ($toolInput.command ?? "").Substring(0, [Math]::Min(200, ($toolInput.command ?? "").Length)) }
    { $_ -in @("Grep", "Glob") } { $subject = $toolInput.pattern }
    "WebFetch" { $subject = $toolInput.url }
    default { $subject = $toolName }
}

$summary = $toolName
if ($subject) {
    $truncSubject = $subject.Substring(0, [Math]::Min(100, $subject.Length))
    $summary = "${toolName}: ${truncSubject}"
}
$desc = $toolInput.description
if ($desc) {
    $truncDesc = $desc.Substring(0, [Math]::Min(80, $desc.Length))
    $summary = "${summary} (${truncDesc})"
}
$summary = $summary.Substring(0, [Math]::Min(500, $summary.Length))

$namespace = if ($cwd) { $cwd.Replace('/', '-').Replace('\', '-').TrimStart('-') } else { "unknown" }

$tagsList = @($toolName.ToLower())
if ($subject) {
    $parts = $subject -split '/'
    if ($parts.Count -gt 1) {
        $tagsList += $parts[-1].ToLower()
    }
}
$tags = $tagsList -join ','

$payload = @{
    session_id = $sessionId
    project = $namespace
    tool_name = $toolName
    subject = $subject
    summary = $summary
    tags = $tags
    event_type = "tool_use"
} | ConvertTo-Json -Compress

try {
    Invoke-RestMethod -Uri $EVENT_URL -Method Post -Body $payload -ContentType "application/json" -TimeoutSec 5 | Out-Null
} catch { }

exit 0
