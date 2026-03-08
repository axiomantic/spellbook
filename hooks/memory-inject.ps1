# memory-inject.ps1 - PostToolUse hook for memory injection (Windows)
#
# FAILURE POLICY: FAIL-OPEN
# Memory injection failures must NEVER prevent tool execution.

$ErrorActionPreference = "SilentlyContinue"

$MCP_PORT = if ($env:SPELLBOOK_MCP_PORT) { $env:SPELLBOOK_MCP_PORT } else { "8765" }
$MCP_HOST = if ($env:SPELLBOOK_MCP_HOST) { $env:SPELLBOOK_MCP_HOST } else { "127.0.0.1" }
$RECALL_URL = "http://${MCP_HOST}:${MCP_PORT}/api/memory/recall"

$FILE_TOOLS = @("Read", "Edit", "Grep", "Glob")

$input_text = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($input_text)) { exit 0 }

try { $data = $input_text | ConvertFrom-Json } catch { exit 0 }

$toolName = $data.tool_name
if ($FILE_TOOLS -notcontains $toolName) { exit 0 }

$toolInput = $data.tool_input
$cwd = $data.cwd

$filePath = ""
switch ($toolName) {
    { $_ -in @("Read", "Edit") } { $filePath = $toolInput.file_path }
    "Grep" { $filePath = $toolInput.path }
    "Glob" { $filePath = $toolInput.path }
}

if ([string]::IsNullOrWhiteSpace($filePath)) { exit 0 }

$namespace = if ($cwd) { $cwd.Replace("/", "-").Replace("\", "-").TrimStart("-") } else { "" }
if ([string]::IsNullOrWhiteSpace($namespace)) { exit 0 }

$payload = @{ file_path = $filePath; namespace = $namespace; limit = 5 } | ConvertTo-Json -Compress

try {
    $response = Invoke-RestMethod -Uri $RECALL_URL -Method Post -Body $payload -ContentType "application/json" -TimeoutSec 3
    $memories = $response.memories
    if ($memories.Count -gt 0) {
        Write-Output "<spellbook-memory>"
        foreach ($mem in $memories[0..([Math]::Min(4, $memories.Count - 1))]) {
            $confidence = if ($mem.status -eq "active") { "verified" } else { "unverified" }
            Write-Output "  <memory type=`"$($mem.memory_type)`" confidence=`"$confidence`" importance=`"$([Math]::Round($mem.importance, 1))`">"
            Write-Output "    $($mem.content)"
            Write-Output "  </memory>"
        }
        Write-Output "</spellbook-memory>"
    }
} catch { }

exit 0
