# Unified spellbook hook entrypoint (Windows)
# Delegates to spellbook_hook.py for all hook logic.

$ErrorActionPreference = "SilentlyContinue"

# Read stdin
$input = [Console]::In.ReadToEnd()

# Find Python
$python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
    @{ error = "Security check failed: python not found on PATH" } | ConvertTo-Json -Compress | Write-Output
    exit 2
}

# Run the Python hook
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$hookScript = Join-Path $scriptDir "spellbook_hook.py"

if (-not (Test-Path $hookScript)) {
    @{ error = "Security check failed: unified hook script not found" } | ConvertTo-Json -Compress | Write-Output
    exit 2
}

$result = $input | & $python.Source $hookScript 2>$null
$exitCode = $LASTEXITCODE

if ($result) {
    Write-Output $result
}

exit $exitCode
