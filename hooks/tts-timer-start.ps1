# hooks/tts-timer-start.ps1
# Claude Code Hook: PreToolUse timer start (writes timestamp files)
# Failure policy: FAIL-OPEN (exit 0 always)

$ErrorActionPreference = "Stop"

try {
    $InputJson = [Console]::In.ReadToEnd()
    if (-not $InputJson) { exit 0 }

    $data = $InputJson | ConvertFrom-Json
    $toolUseId = $data.tool_use_id
    if (-not $toolUseId) { exit 0 }

    # Validate tool_use_id against path traversal
    if ($toolUseId -match '[\\\\/]' -or $toolUseId -match '\.\.' -or $toolUseId -match '\s') {
        exit 0
    }

    $now = [int][double]::Parse(
        (New-TimeSpan -Start (Get-Date "1970-01-01") -End (Get-Date).ToUniversalTime()).TotalSeconds.ToString("F0")
    )
    $tempDir = [System.IO.Path]::GetTempPath()

    # Write TTS timer file
    try {
        $ttsFile = Join-Path $tempDir "claude-tool-start-$toolUseId"
        [System.IO.File]::WriteAllText($ttsFile, $now.ToString())
    } catch { }

    # Write notification timer file
    try {
        $notifyFile = Join-Path $tempDir "claude-notify-start-$toolUseId"
        [System.IO.File]::WriteAllText($notifyFile, $now.ToString())
    } catch { }

    exit 0
} catch {
    exit 0
}
