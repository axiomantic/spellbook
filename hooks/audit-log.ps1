# hooks/audit-log.ps1
# Claude Code Hook: PostToolUse audit logging
# Failure policy: FAIL-OPEN (exit 0 always)

$ErrorActionPreference = "Stop"

try {
    $InputJson = [Console]::In.ReadToEnd()
    if (-not $InputJson) { exit 0 }

    if ($env:SPELLBOOK_DIR) {
        $ProjectRoot = $env:SPELLBOOK_DIR
    } else {
        $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
        $ProjectRoot = Split-Path -Parent $ScriptDir
    }

    $env:PYTHONPATH = $ProjectRoot
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo.FileName = "python3"
    $process.StartInfo.Arguments = "-m spellbook_mcp.security.check --mode audit"
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.RedirectStandardInput = $true
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $process.StartInfo.WorkingDirectory = $ProjectRoot
    $process.StartInfo.EnvironmentVariables["PYTHONPATH"] = $ProjectRoot
    $process.Start() | Out-Null
    $process.StandardInput.Write($InputJson)
    $process.StandardInput.Close()
    $process.StandardOutput.ReadToEnd() | Out-Null
    $process.WaitForExit(10000) | Out-Null

    exit 0
} catch {
    exit 0
}
