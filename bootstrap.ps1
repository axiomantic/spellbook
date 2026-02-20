# bootstrap.ps1 - Spellbook installer for Windows
# Usage: irm https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.ps1 | iex
$ErrorActionPreference = "Stop"

Write-Host "Spellbook Installer for Windows" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Check for Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[error] Python is required but not found." -ForegroundColor Red
    Write-Host "Install Python from https://python.org or via:" -ForegroundColor Yellow
    Write-Host "  winget install Python.Python.3.12" -ForegroundColor Yellow
    exit 1
}

# Check Python version
$pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$major, $minor = $pyVersion -split '\.'
if ([int]$major -lt 3 -or ([int]$major -eq 3 -and [int]$minor -lt 10)) {
    Write-Host "[error] Python 3.10+ is required. Found: $pyVersion" -ForegroundColor Red
    exit 1
}

# Install uv if missing
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "> Installing uv (Python package manager)..." -ForegroundColor Blue
    irm https://astral.sh/uv/install.ps1 | iex
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
}

# Check for git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[error] Git is required but not found." -ForegroundColor Red
    Write-Host "Install Git for Windows:" -ForegroundColor Yellow
    Write-Host "  winget install Git.Git" -ForegroundColor Yellow
    Write-Host "  or download from https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

# Clone repo if not already present
$installDir = "$env:LOCALAPPDATA\spellbook"
if (-not (Test-Path $installDir)) {
    Write-Host "> Cloning spellbook repository..." -ForegroundColor Blue
    git clone https://github.com/axiomantic/spellbook.git $installDir
}

# Run installer
Write-Host "> Running spellbook installer..." -ForegroundColor Blue
uv run "$installDir\install.py" --yes
