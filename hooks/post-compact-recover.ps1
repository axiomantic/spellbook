# hooks/post-compact-recover.ps1
# Claude Code Hook: SessionStart - inject recovery context after compaction
# Failure policy: FAIL-OPEN (exit 0 always - must NEVER prevent session start)

$ErrorActionPreference = "Stop"

$McpHost = if ($env:SPELLBOOK_MCP_HOST) { $env:SPELLBOOK_MCP_HOST } else { "127.0.0.1" }
$McpPort = if ($env:SPELLBOOK_MCP_PORT) { $env:SPELLBOOK_MCP_PORT } else { "8765" }
$McpUrl = "http://${McpHost}:${McpPort}/mcp"
$LogDir = Join-Path $HOME ".local" "spellbook" "logs"
$LogFile = Join-Path $LogDir "post-compact.log"

function Write-Log {
    param([string]$Message)
    try {
        if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $LogFile -Value "[$timestamp] [post-compact-recover] $Message"
    } catch { }
}

function Output-Fallback {
    $directive = "COMPACTION OCCURRED. Call spellbook_session_init to restore workflow state."
    $output = @{
        hookSpecificOutput = @{
            hookEventName = "SessionStart"
            additionalContext = $directive
        }
    } | ConvertTo-Json -Depth 5 -Compress
    Write-Output $output
    exit 0
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
        -TimeoutSec 3

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
    if (-not $InputJson) { exit 0 }

    $data = $InputJson | ConvertFrom-Json
    $source = if ($data.source) { $data.source } else { "" }
    $cwd = if ($data.cwd) { $data.cwd } else { "" }

    # Only act on compaction events
    if ($source -ne "compact") { exit 0 }
    if (-not $cwd) { Output-Fallback }

    Write-Log "Post-compact recovery for: $cwd"

    # Load workflow state
    $loadResult = Invoke-McpTool -ToolName "workflow_state_load" -Arguments @{
        project_path = $cwd
        max_age_hours = 24
    }

    if (-not $loadResult -or -not $loadResult.found) {
        Write-Log "No workflow state found"
        Output-Fallback
    }

    $state = $loadResult.state

    # Extract state fields
    $activeSkill = if ($state.active_skill) { $state.active_skill } else { "" }
    $skillPhase = if ($state.skill_phase) { $state.skill_phase } else { "" }
    $bindingDecisions = if ($state.binding_decisions) { $state.binding_decisions } else { "" }
    $nextAction = if ($state.next_action) { $state.next_action } else { "" }
    $workflowPattern = if ($state.workflow_pattern) { $state.workflow_pattern } else { "" }

    # Build recovery directive
    $directive = @"
# POST-COMPACTION RECOVERY DIRECTIVE

## Active Workflow
"@

    if ($activeSkill) {
        $directive += "`n- **Active Skill:** $activeSkill"
        if ($skillPhase) { $directive += " (phase: $skillPhase)" }
    }
    if ($workflowPattern) {
        $directive += "`n- **Workflow Pattern:** $workflowPattern"
    }

    # Optionally fetch skill constraints
    if ($activeSkill) {
        try {
            $skillResult = Invoke-McpTool -ToolName "skill_instructions_get" -Arguments @{
                skill_name = $activeSkill
                sections = @("FORBIDDEN", "REQUIRED")
            }
            if ($skillResult -and $skillResult.instructions) {
                $directive += "`n`n## Skill Constraints`n$($skillResult.instructions)"
            }
        } catch {
            Write-Log "Failed to fetch skill constraints: $_"
        }
    }

    if ($bindingDecisions) {
        $directive += "`n`n## Binding Decisions`n$bindingDecisions"
    }

    if ($nextAction) {
        $directive += "`n`n## Next Action`n$nextAction"
    }

    $directive += "`n`nCall ``spellbook_session_init`` to fully restore session context."

    # Output as hookSpecificOutput JSON
    $output = @{
        hookSpecificOutput = @{
            hookEventName = "SessionStart"
            additionalContext = $directive
        }
    } | ConvertTo-Json -Depth 5 -Compress
    Write-Output $output
    Write-Log "Recovery directive output successfully"
    exit 0
} catch {
    Write-Log "Error: $_"
    Output-Fallback
}
