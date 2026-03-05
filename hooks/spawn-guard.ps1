# hooks/spawn-guard.ps1
# Claude Code Hook: PreToolUse gate for spawn_claude_session
# Failure policy: FAIL-CLOSED (exit 2 on any error)

$ErrorActionPreference = "Stop"

function Block-Tool {
    param([string]$Reason = "Security check unavailable")
    @{ error = $Reason } | ConvertTo-Json -Compress | Write-Output
    exit 2
}

try {
    if ($env:SPELLBOOK_DIR) {
        $ProjectRoot = $env:SPELLBOOK_DIR
    } else {
        $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
        $ProjectRoot = Split-Path -Parent $ScriptDir
    }

    $CheckModule = Join-Path $ProjectRoot "spellbook_mcp" "security" "check.py"
    if (-not (Test-Path $CheckModule)) {
        Block-Tool "Security check failed: check module not found"
    }

    $InputJson = [Console]::In.ReadToEnd()
    if (-not $InputJson) {
        Block-Tool "Security check failed: no input received"
    }

    # Normalize tool_name for check.py routing
    try {
        $data = $InputJson | ConvertFrom-Json
        $data.tool_name = "spawn_claude_session"
        $InputJson = $data | ConvertTo-Json -Depth 10 -Compress
    } catch {
        Block-Tool "Security check failed: input normalization error"
    }

    $env:PYTHONPATH = $ProjectRoot
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo.FileName = "python3"
    $process.StartInfo.Arguments = "-m spellbook_mcp.security.check"
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.RedirectStandardInput = $true
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $process.StartInfo.WorkingDirectory = $ProjectRoot
    $process.StartInfo.EnvironmentVariables["PYTHONPATH"] = $ProjectRoot
    $process.Start() | Out-Null
    $process.StandardInput.Write($InputJson)
    $process.StandardInput.Close()
    $stdout = $process.StandardOutput.ReadToEnd()
    $process.WaitForExit(30000) | Out-Null

    switch ($process.ExitCode) {
        0 { exit 0 }
        2 {
            if ($stdout.Trim()) {
                Write-Output $stdout.Trim()
            } else {
                @{ error = "Security check failed: blocked by policy" } | ConvertTo-Json -Compress | Write-Output
            }
            exit 2
        }
        default {
            Block-Tool "Security check failed: internal error"
        }
    }
} catch {
    Block-Tool "Security check failed: internal error"
}
