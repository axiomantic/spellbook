# hooks/notify-on-complete.ps1
# Claude Code Hook: PostToolUse OS notification
# Failure policy: FAIL-OPEN (exit 0 always)

$ErrorActionPreference = "Stop"

try {
    $InputJson = [Console]::In.ReadToEnd()
    if (-not $InputJson) { exit 0 }

    $data = $InputJson | ConvertFrom-Json

    $toolName = if ($data.tool_name) { $data.tool_name } else { "" }
    $toolUseId = if ($data.tool_use_id) { $data.tool_use_id } else { "" }

    # Check if notifications are enabled
    $notifyEnabled = if ($env:SPELLBOOK_NOTIFY_ENABLED) { $env:SPELLBOOK_NOTIFY_ENABLED } else { "true" }
    if ($notifyEnabled.ToLower() -ne "true") { exit 0 }

    # Blacklist: interactive/management tools
    $blacklist = @(
        "AskUserQuestion", "TodoRead", "TodoWrite",
        "TaskCreate", "TaskUpdate", "TaskGet", "TaskList"
    )
    if ($toolName -in $blacklist) { exit 0 }

    # Validate tool_use_id
    if (-not $toolUseId -or $toolUseId -match '[\\\\/]' -or $toolUseId -match '\.\.' -or $toolUseId -match '\s') {
        exit 0
    }

    # Read and delete timer file
    $tempDir = [System.IO.Path]::GetTempPath()
    $startFile = Join-Path $tempDir "claude-notify-start-$toolUseId"
    if (-not (Test-Path $startFile)) { exit 0 }

    try {
        $startTime = [int](Get-Content $startFile -Raw).Trim()
        Remove-Item $startFile -Force
    } catch {
        exit 0
    }

    # Check threshold
    $threshold = if ($env:SPELLBOOK_NOTIFY_THRESHOLD) { [int]$env:SPELLBOOK_NOTIFY_THRESHOLD } else { 30 }
    $now = [int][double]::Parse(
        (New-TimeSpan -Start (Get-Date "1970-01-01") -End (Get-Date).ToUniversalTime()).TotalSeconds.ToString("F0")
    )
    $elapsed = $now - $startTime
    if ($elapsed -lt $threshold) { exit 0 }

    # Build notification
    $title = if ($env:SPELLBOOK_NOTIFY_TITLE) { $env:SPELLBOOK_NOTIFY_TITLE } else { "Spellbook" }
    $body = "$toolName finished (${elapsed}s)"

    # Escape single quotes for PowerShell string embedding
    $safeTitle = $title.Replace("'", "''")
    $safeBody = $body.Replace("'", "''")

    # Send Windows toast notification
    $psScript = @"
try {
    Import-Module BurntToast -ErrorAction Stop
    New-BurntToastNotification -Text '$safeTitle','$safeBody'
} catch {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    `$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    `$textNodes = `$template.GetElementsByTagName('text')
    `$textNodes.Item(0).AppendChild(`$template.CreateTextNode('$safeTitle')) | Out-Null
    `$textNodes.Item(1).AppendChild(`$template.CreateTextNode('$safeBody')) | Out-Null
    `$toast = [Windows.UI.Notifications.ToastNotification]::new(`$template)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Spellbook').Show(`$toast)
}
"@

    # Prefer pwsh over legacy powershell.
    # NOTE: This uses Get-Command (PATH-based lookup), which is an intentional
    # improvement over the .py version's hardcoded System32 path check. PATH-based
    # detection works for all pwsh install locations (winget, scoop, manual).
    $shell = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }

    Start-Process -FilePath $shell -ArgumentList "-Command", $psScript -NoNewWindow -Wait
    exit 0
} catch {
    exit 0
}
