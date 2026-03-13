# hooks/tts-notify.ps1
# Claude Code Hook: PostToolUse TTS notification
# Failure policy: FAIL-OPEN (exit 0 always)

$ErrorActionPreference = "Stop"

try {
    $InputJson = [Console]::In.ReadToEnd()
    if (-not $InputJson) { exit 0 }

    $data = $InputJson | ConvertFrom-Json

    $toolName = if ($data.tool_name) { $data.tool_name } else { "" }
    $toolUseId = if ($data.tool_use_id) { $data.tool_use_id } else { "" }

    # Blacklist: interactive/management tools
    $blacklist = @(
        "AskUserQuestion", "TodoRead", "TodoWrite",
        "TaskCreate", "TaskUpdate", "TaskGet", "TaskList"
    )
    if ($toolName -in $blacklist) { exit 0 }
    if (-not $toolUseId) { exit 0 }

    # Validate tool_use_id against path traversal
    if ($toolUseId -match '[\\\\/]' -or $toolUseId -match '\.\.' -or $toolUseId -match '\s') {
        exit 0
    }

    # Read and delete timer file
    $tempDir = [System.IO.Path]::GetTempPath()
    $startFile = Join-Path $tempDir "claude-tool-start-$toolUseId"
    if (-not (Test-Path $startFile)) { exit 0 }

    try {
        $startTime = [int](Get-Content $startFile -Raw).Trim()
        Remove-Item $startFile -Force
    } catch {
        exit 0
    }

    # Check threshold
    $threshold = if ($env:SPELLBOOK_TTS_THRESHOLD) { [int]$env:SPELLBOOK_TTS_THRESHOLD } else { 30 }
    $now = [int][double]::Parse(
        (New-TimeSpan -Start (Get-Date "1970-01-01") -End (Get-Date).ToUniversalTime()).TotalSeconds.ToString("F0")
    )
    $elapsed = $now - $startTime
    if ($elapsed -lt $threshold) { exit 0 }

    # Build message
    $cwd = if ($data.cwd) { $data.cwd } else { "" }
    $project = if ($cwd) { Split-Path $cwd -Leaf } else { "unknown" }

    $detail = ""
    $inp = $data.tool_input
    if ($toolName -eq "Bash" -and $inp -and $inp.command) {
        $cmd = $inp.command.ToString()
        $parts = $cmd -split '\s+', 2
        if ($parts.Count -gt 0) {
            $detail = Split-Path $parts[0] -Leaf
        }
    } elseif ($toolName -eq "Task" -and $inp -and $inp.description) {
        $detail = $inp.description.ToString().Substring(0, [Math]::Min(40, $inp.description.ToString().Length))
    }

    $msgParts = @($project, $toolName)
    if ($detail) { $msgParts += $detail }
    $msgParts += "finished"
    $message = $msgParts -join " "

    # Send to MCP speak endpoint
    $mcpHost = if ($env:SPELLBOOK_MCP_HOST) { $env:SPELLBOOK_MCP_HOST } else { "127.0.0.1" }
    $mcpPort = if ($env:SPELLBOOK_MCP_PORT) { $env:SPELLBOOK_MCP_PORT } else { "8765" }
    $speakUrl = "http://${mcpHost}:${mcpPort}/api/speak"
    $tokenFile = Join-Path $HOME ".local" "spellbook" ".mcp-token"
    $authHeaders = @{}
    if (Test-Path $tokenFile) {
        $tkn = (Get-Content $tokenFile -Raw).Trim()
        if ($tkn) { $authHeaders["Authorization"] = "Bearer $tkn" }
    }

    $body = @{ text = $message } | ConvertTo-Json -Compress
    try {
        Invoke-WebRequest -Uri $speakUrl -Method Post -Body $body -ContentType "application/json" -Headers $authHeaders -TimeoutSec 10 | Out-Null
    } catch { }

    exit 0
} catch {
    exit 0
}
