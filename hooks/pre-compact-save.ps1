# hooks/pre-compact-save.ps1
# Claude Code Hook: PreCompact - save workflow state before compaction
# Failure policy: FAIL-OPEN (exit 0 always - must NEVER block compaction)

$ErrorActionPreference = "Stop"

$McpHost = if ($env:SPELLBOOK_MCP_HOST) { $env:SPELLBOOK_MCP_HOST } else { "127.0.0.1" }
$McpPort = if ($env:SPELLBOOK_MCP_PORT) { $env:SPELLBOOK_MCP_PORT } else { "8765" }
$McpUrl = "http://${McpHost}:${McpPort}/mcp"
$LogDir = Join-Path $HOME ".local" "spellbook" "logs"
$LogFile = Join-Path $LogDir "pre-compact.log"

function Write-Log {
    param([string]$Message)
    try {
        if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $LogFile -Value "[$timestamp] [pre-compact-save] $Message"
    } catch { }
}

function Invoke-McpTool {
    param([string]$ToolName, [hashtable]$Arguments)
    $body = @{
        jsonrpc = "2.0"
        id = 1
        method = "tools/call"
        params = @{
            name = $ToolName
            arguments = $Arguments
        }
    } | ConvertTo-Json -Depth 10 -Compress

    $response = Invoke-WebRequest -Uri $McpUrl -Method Post -Body $body `
        -ContentType "application/json" `
        -Headers @{ Accept = "application/json, text/event-stream" } `
        -TimeoutSec 2

    # Parse SSE response: look for data: lines with result
    $result = $null
    foreach ($line in $response.Content -split "`n") {
        $line = $line.Trim()
        if ($line.StartsWith("data: ")) {
            try {
                $parsed = $line.Substring(6) | ConvertFrom-Json
                if ($parsed.result) {
                    if ($parsed.result.structuredContent) {
                        $result = $parsed.result.structuredContent
                        break
                    }
                    if ($parsed.result.content) {
                        foreach ($item in $parsed.result.content) {
                            if ($item.type -eq "text") {
                                try {
                                    $result = $item.text | ConvertFrom-Json
                                    break
                                } catch { }
                            }
                        }
                        if ($result) { break }
                    }
                }
            } catch { continue }
        }
    }
    return $result
}

try {
    # Read stdin JSON
    $InputJson = [Console]::In.ReadToEnd()
    if (-not $InputJson) {
        Write-Log "Empty stdin, exiting"
        exit 0
    }

    $data = $InputJson | ConvertFrom-Json
    $projectPath = if ($data.cwd) { $data.cwd } else { "" }
    if (-not $projectPath) {
        Write-Log "No cwd in stdin JSON, exiting"
        exit 0
    }

    Write-Log "Project path: $projectPath"

    # Step 1: Load current state
    Write-Log "Checking for existing workflow state"
    $loadResult = Invoke-McpTool -ToolName "workflow_state_load" -Arguments @{
        project_path = $projectPath
        max_age_hours = 24
    }
    if (-not $loadResult) {
        Write-Log "MCP daemon unreachable or workflow_state_load failed, exiting"
        exit 0
    }

    # Step 2: Check freshness
    $found = $loadResult.found
    $ageHours = $loadResult.age_hours
    if ($found -and $ageHours -ne $null -and [double]$ageHours -lt 0.083) {
        Write-Log "Workflow state is fresh (< 5 min old), nothing to do"
        exit 0
    }

    # Step 3: Save state
    Write-Log "Saving workflow state (trigger=auto)"
    $existingState = if ($loadResult.state) { $loadResult.state } else { @{} }

    # Convert PSCustomObject to hashtable for merging
    $state = @{}
    if ($existingState -is [PSCustomObject]) {
        $existingState.PSObject.Properties | ForEach-Object { $state[$_.Name] = $_.Value }
    } elseif ($existingState -is [hashtable]) {
        $state = $existingState.Clone()
    }
    if (-not $state.ContainsKey("compaction_flag")) {
        $state["compaction_flag"] = $true
    }

    $saveResult = Invoke-McpTool -ToolName "workflow_state_save" -Arguments @{
        project_path = $projectPath
        state = $state
        trigger = "auto"
    }

    Write-Log "Save result: $($saveResult | ConvertTo-Json -Compress)"
    Write-Log "Pre-compact save complete"
    exit 0
} catch {
    Write-Log "Error: $_"
    exit 0
}
