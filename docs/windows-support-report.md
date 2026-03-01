# Windows Support Report

**Date:** 2026-02-20
**Branch:** `elijahr/auto-update`
**Status:** Brainstorm / Planning

---

## 1. Executive Summary

Spellbook currently supports macOS and Linux across five coding agent platforms (Claude Code, OpenCode, Codex, Gemini CLI, Crush). Adding Windows support requires changes across four major areas:

1. **Path handling and config locations** — translating Unix conventions (`~/.local/`, `~/.config/`) to Windows equivalents (`%APPDATA%`, `%LOCALAPPDATA%`)
2. **Symlink management** — Windows requires admin privileges or Developer Mode for symlinks; fallback strategies (junctions, copies) are needed
3. **Service/daemon management** — replacing launchd (macOS) and systemd (Linux) with Windows Task Scheduler
4. **Shell scripts and hooks** — 5 bash hook scripts and a bash bootstrap script need PowerShell or Python equivalents

The core Python installer and MCP server are already cross-platform in structure (using `pathlib.Path`, `platform.system()`). The effort is primarily in the platform-specific integration points.

---

## 2. Current State Analysis

### Supported Platforms

| Platform | Config Location | MCP Transport | Installer File |
|----------|----------------|---------------|----------------|
| Claude Code | `~/.claude/` | HTTP daemon | `installer/platforms/claude_code.py` |
| OpenCode | `~/.config/opencode/` | HTTP daemon | `installer/platforms/opencode.py` |
| Codex | `~/.codex/` | HTTP daemon | `installer/platforms/codex.py` |
| Gemini CLI | `~/.gemini/` | HTTP daemon | `installer/platforms/gemini.py` |
| Crush | `~/.local/share/crush/` | HTTP daemon | `installer/platforms/crush.py` |

### How Installation Works Today

1. `bootstrap.sh` (bash) bootstraps `uv` and runs `install.py`
2. `install.py` detects the OS (macOS/Linux), installs dependencies, detects available platforms
3. Per-platform installers create symlinks for skills/commands, write context files (CLAUDE.md, AGENTS.md), and register MCP servers
4. `installer/components/mcp.py` installs a daemon via launchd (macOS) or systemd (Linux)
5. `installer/components/symlinks.py` creates symlinks for all skill/command directories
6. Hook scripts (bash) are installed for security gates

### Key Architecture Files

| File | Lines | Role |
|------|-------|------|
| `install.py` | ~765 | Entry point, OS detection, dependency management |
| `installer/config.py` | ~94 | Platform config paths and defaults |
| `installer/components/symlinks.py` | ~389 | Symlink creation, cleanup, verification |
| `installer/components/mcp.py` | ~525 | Daemon management (launchd/systemd) |
| `installer/demarcation.py` | ~262 | Context file section management |
| `bootstrap.sh` | ~77 | Bash bootstrap script |

---

## 3. Installer Changes Required

### 3.1 Path Handling (`installer/config.py`)

Current paths use Unix conventions via `Path.home()`. While `Path.home()` works on Windows (`C:\Users\<user>`), the subdirectory conventions differ.

**Proposed Windows path mapping:**

| Purpose | Current (Unix) | Proposed (Windows) |
|---------|---------------|-------------------|
| Spellbook install | `~/.local/share/spellbook` | `%LOCALAPPDATA%\spellbook` |
| Spellbook config | `~/.local/spellbook` | `%APPDATA%\spellbook` |
| Claude Code | `~/.claude/` | `%USERPROFILE%\.claude\` (Claude Code's own convention) |
| OpenCode | `~/.config/opencode/` | `%APPDATA%\opencode\` |
| Codex | `~/.codex/` | `%USERPROFILE%\.codex\` |
| Gemini CLI | `~/.gemini/` | `%USERPROFILE%\.gemini\` |
| Crush | `~/.local/share/crush/` | `%LOCALAPPDATA%\crush\` |

**Implementation approach:**
- Add a `get_platform_paths()` function in `installer/config.py` that returns OS-appropriate paths
- Use `os.environ.get("LOCALAPPDATA")` and `os.environ.get("APPDATA")` on Windows
- Verify actual config locations by checking what each tool uses on Windows (some may use `%USERPROFILE%` dot-directories even on Windows)

### 3.2 OS Detection (`install.py`)

The installer already uses `platform.system()` in places. Changes needed:

- **Line ~211**: `sh -c "curl ... | sh"` for uv installation — needs `powershell -c "irm ... | iex"` equivalent
- **Line ~220+**: Distro detection reads `/etc/os-release` — skip on Windows
- **Lines ~342-366**: Git installation via `apt`/`brew` — needs `winget` or manual instructions
- **Line ~628**: `DEFAULT_INSTALL_DIR` uses `~/.local/share/spellbook`

### 3.3 Symlink Strategy (`installer/components/symlinks.py`)

This is the **highest-risk area**. The installer creates 178+ symlinks across skill/command directories.

**Windows symlink constraints:**
- NTFS symlinks require either Administrator privileges or Windows 10+ Developer Mode
- Directory junctions (`mklink /J`) work without elevation but are directory-only
- File hardlinks work without elevation but are file-only and same-volume

**Proposed fallback chain:**

```
1. Try os.symlink() (works if admin or dev mode)
   ↓ fails
2. Try directory junction via subprocess (mklink /J)
   ↓ fails
3. Fall back to shutil.copytree() with update-on-install
   ↓ always works
4. Warn user about limitations of copy mode
```

**New code needed in `symlinks.py`:**

```python
def create_link(source: Path, target: Path) -> str:
    """Create a link with platform-appropriate fallback."""
    if sys.platform == "win32":
        return _create_windows_link(source, target)
    else:
        target.symlink_to(source)
        return "symlink"

def _create_windows_link(source: Path, target: Path) -> str:
    """Try symlink -> junction -> copy on Windows."""
    try:
        target.symlink_to(source)
        return "symlink"
    except OSError:
        pass

    if source.is_dir():
        try:
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                check=True, capture_output=True
            )
            return "junction"
        except subprocess.CalledProcessError:
            pass

    if source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)
    return "copy"
```

**Impact on updates:** Copy mode means skills/commands won't auto-update when the spellbook repo changes. The auto-update system would need to re-copy on update.

---

## 4. Shell and Script Changes

### 4.1 Bootstrap Script

**Current:** `bootstrap.sh` (bash-only, 77 lines)

**Needed:** `bootstrap.ps1` (PowerShell equivalent)

```powershell
# bootstrap.ps1 - Windows bootstrap for spellbook
# Checks for Python/uv, clones repo, runs install.py
```

Also consider a `bootstrap.bat` one-liner that invokes PowerShell for users who aren't in a PowerShell terminal.

### 4.2 Hook Scripts (5 files in `hooks/`)

| Hook | Purpose | Windows Strategy |
|------|---------|-----------------|
| `bash-gate.sh` | PreToolUse: gate bash commands | Python wrapper |
| `spawn-guard.sh` | PreToolUse: gate spawn operations | Python wrapper |
| `state-sanitize.sh` | PreToolUse: sanitize state saves | Python wrapper |
| `audit-log.sh` | PostToolUse: audit logging | Python wrapper |
| `canary-check.sh` | PostToolUse: canary token checking | Python wrapper |

**Recommended approach:** Create Python wrapper scripts (`hooks/*.py`) that work cross-platform. The installer detects the OS and registers the appropriate hook type. Most hook logic is simple string matching and file operations that translate directly to Python.

### 4.3 Other Shell Scripts

| Script | Current | Windows Need |
|--------|---------|-------------|
| `scripts/install-hooks.sh` | Bash, installs git hooks | Python or PowerShell equivalent |
| `scripts/spellbook-server.py` | Python | Already cross-platform |
| `scripts/generate_docs.py` | Python | Already cross-platform |
| `scripts/auto_update.py` | Python | Already cross-platform |

---

## 5. MCP Server Changes (`spellbook_mcp/`)

### 5.1 HTTP Daemon

The MCP server (`spellbook_mcp/server.py`) uses FastMCP/FastAPI on `127.0.0.1:8765`. This is already cross-platform — no changes needed for the server itself.

### 5.2 Daemon Management (`installer/components/mcp.py`)

**Current support:**
- macOS: launchd plist at `~/Library/LaunchAgents/com.spellbook.mcp.plist`
- Linux: systemd unit at `~/.config/systemd/user/spellbook-mcp.service`

**Windows needs: Task Scheduler integration**

```python
def install_windows_task(server_path: Path, python_path: Path):
    """Register MCP server as a Windows scheduled task."""
    task_name = "SpellbookMCP"
    cmd = f'"{python_path}" "{server_path}"'

    subprocess.run([
        "schtasks", "/create",
        "/tn", task_name,
        "/tr", cmd,
        "/sc", "onlogon",
        "/rl", "limited",
        "/f"  # force overwrite
    ], check=True)

def uninstall_windows_task():
    subprocess.run([
        "schtasks", "/delete",
        "/tn", "SpellbookMCP",
        "/f"
    ], check=True)

def is_windows_task_running():
    result = subprocess.run(
        ["schtasks", "/query", "/tn", "SpellbookMCP"],
        capture_output=True, text=True
    )
    return "Running" in result.stdout
```

### 5.3 Process Management

**Current:** Uses `pgrep`/`pkill` for process detection and termination (`mcp.py` lines 237-268).

**Windows equivalent:**

```python
if sys.platform == "win32":
    # Find process
    result = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq python.exe", "/FO", "CSV"],
        capture_output=True, text=True
    )
    # Kill process
    subprocess.run(["taskkill", "/F", "/PID", str(pid)])
else:
    subprocess.run(["pgrep", "-f", "spellbook_mcp/server.py"])
    subprocess.run(["pkill", "-9", "-f", "spellbook_mcp/server.py"])
```

### 5.4 Terminal Spawning

`spellbook_mcp/terminal_utils.py` detects Unix terminals (xterm, gnome-terminal, etc.) and spawns sessions. Windows needs:

- `cmd.exe /K` for Command Prompt
- `powershell.exe -NoExit -Command` for PowerShell
- Windows Terminal (`wt.exe`) detection for modern Windows

---

## 6. Platform-Specific Windows Config Locations

Research needed to confirm actual Windows config paths for each tool:

| Tool | Likely Windows Config | Verification Method |
|------|----------------------|---------------------|
| Claude Code | `%USERPROFILE%\.claude\` | Check Claude Code Windows installer docs |
| OpenCode | `%APPDATA%\opencode\` | Check opencode source for Windows paths |
| Codex | `%USERPROFILE%\.codex\` | Check codex source for Windows paths |
| Gemini CLI | `%USERPROFILE%\.gemini\` | Check gemini-cli source for Windows paths |
| Crush | `%LOCALAPPDATA%\crush\` | Check crush source for Windows paths |

**Action item:** Before implementation, verify each tool's actual Windows config location by checking their source code or documentation. Some tools may use dot-directories under `%USERPROFILE%` even on Windows.

---

## 7. Documentation Needed

### 7.1 Quick Start Guide for Windows

Create `docs/getting-started/windows.md`:

```markdown
# Windows Quick Start

## Prerequisites
- Windows 10 version 1903+ or Windows 11
- Python 3.10+ (via Microsoft Store, python.org, or winget)
- Git for Windows
- (Recommended) Windows Terminal
- (Recommended) Developer Mode enabled (Settings > Developer Settings)

## Installation

### Option A: PowerShell (recommended)
powershell -c "irm https://raw.githubusercontent.com/.../bootstrap.ps1 | iex"

### Option B: Manual
git clone https://github.com/.../spellbook.git
cd spellbook
python install.py

## Developer Mode (for symlinks)
Settings > Privacy & Security > For Developers > Developer Mode: On
Without this, spellbook uses directory junctions (slightly less flexible).

## Troubleshooting
- Symlink errors: Enable Developer Mode or run as Administrator
- Script execution policy: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
- Path too long: Enable long paths in Group Policy
```

### 7.2 Other Documentation Updates

| Document | Changes Needed |
|----------|---------------|
| `README.md` | Add Windows to supported platforms, Windows install command |
| `docs/getting-started/` | Add Windows quick start alongside existing guides |
| `docs/reference/` | Document Windows-specific config locations |
| `docs/contributing/` | Add Windows development setup instructions |
| `AGENTS.spellbook.md` | Note Windows support in the user-facing template |

---

## 8. Testing Strategy

### 8.1 CI/CD Additions

Add to `.github/workflows/test.yml`:

```yaml
jobs:
  test:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.10", "3.11", "3.12"]
    runs-on: ${{ matrix.os }}
```

### 8.2 Windows-Specific Test Cases

| Area | Test Cases |
|------|-----------|
| Path handling | Config paths resolve correctly on Windows |
| Symlinks | Symlink creation with admin, junction fallback, copy fallback |
| Daemon | Task Scheduler registration and removal |
| Bootstrap | PowerShell bootstrap script completes successfully |
| Hooks | Python hook wrappers fire correctly |
| MCP server | HTTP server starts and responds on Windows |
| Install/uninstall | Full round-trip install and clean uninstall |
| Long paths | Paths > 260 chars handled correctly |
| Spaces in paths | `C:\Users\John Smith\` handled correctly |

### 8.3 Manual Testing Checklist

- [ ] Fresh Windows 10 install (no Developer Mode)
- [ ] Fresh Windows 11 install (with Developer Mode)
- [ ] Install with each supported tool (Claude Code, OpenCode, Codex, Gemini CLI, Crush)
- [ ] Uninstall cleanly removes all artifacts
- [ ] Auto-update works on Windows
- [ ] MCP server survives restart
- [ ] Hooks fire correctly in each tool

### 8.4 Docker-Based Integration Tests

The existing Docker integration tests (`tests/integration/docker/`) are Linux-only. Windows containers could be added but are significantly more complex. Recommend relying on GitHub Actions `windows-latest` runners instead.

---

## 9. Known Risks and Gotchas

### 9.1 Symlink Permissions (HIGH RISK)
Windows symlinks require either Administrator privileges or Developer Mode (Win10 1703+). Many users won't have either. The junction/copy fallback is essential.

### 9.2 Path Length Limits (MEDIUM RISK)
Windows has a 260-character path limit by default. Deeply nested skill paths could hit this. Mitigation: enable long path support via registry or manifest, and keep installed paths shallow.

### 9.3 PowerShell Execution Policy (MEDIUM RISK)
Default PowerShell execution policy blocks unsigned scripts. The bootstrap script and any PowerShell hooks need to handle `Set-ExecutionPolicy` or use `-ExecutionPolicy Bypass`.

### 9.4 Line Endings (LOW RISK)
Git on Windows may convert LF to CRLF. Skill/command files should work with either, but `.gitattributes` should enforce LF for shell scripts.

### 9.5 Encoding (LOW RISK)
Windows console uses CP-1252 by default, not UTF-8. Python 3.10+ defaults to UTF-8 mode, but subprocess output may need explicit encoding handling.

### 9.6 File Locking (LOW RISK)
Windows locks files that are open by other processes. Updating skills/commands while the MCP server is running could fail. May need to stop the server before updates.

### 9.7 Antivirus Interference (LOW RISK)
Windows Defender or other AV may flag the MCP server or hook scripts. May need to document adding exclusions.

---

## 10. Recommended Implementation Order

### Phase 1: Foundation (Core Paths + Basic Install)

**Goal:** `python install.py` works on Windows, installs context files

1. Add Windows path resolution to `installer/config.py`
2. Add Windows branch to `install.py` (skip distro detection, use `winget`/manual for deps)
3. Create `bootstrap.ps1`
4. Use copy-based installation (skip symlinks initially)
5. Skip daemon installation (manual server start)
6. Skip hooks (document as not-yet-supported)
7. Add basic Windows CI job

**Result:** Users can install spellbook on Windows with reduced functionality.

### Phase 2: Symlinks and Skills

**Goal:** Skills and commands are properly linked/copied

1. Implement symlink fallback chain in `symlinks.py` (symlink -> junction -> copy)
2. Add Developer Mode detection
3. Update all platform installers to use the new link abstraction
4. Add symlink-related tests for Windows

**Result:** Full skill/command availability on Windows.

### Phase 3: Service Management

**Goal:** MCP server runs as a background service

1. Add Task Scheduler support in `mcp.py`
2. Replace `pgrep`/`pkill` with `tasklist`/`taskkill` on Windows
3. Add Windows terminal detection in `terminal_utils.py`
4. Test daemon lifecycle (install, start, stop, uninstall)

**Result:** MCP server auto-starts on Windows login.

### Phase 4: Hooks and Security

**Goal:** Hook scripts work on Windows

1. Create Python wrapper versions of all 5 hook scripts
2. Update hook installer to register Python wrappers on Windows
3. Test hooks with each supported tool on Windows

**Result:** Security hooks fire on Windows.

### Phase 5: Documentation and Polish

**Goal:** Windows is a first-class supported platform

1. Write Windows Quick Start guide
2. Update README with Windows installation
3. Add Windows troubleshooting guide
4. Full CI matrix (Windows 10, 11, with/without Developer Mode)
5. Update `AGENTS.spellbook.md` template for Windows users

**Result:** Complete Windows support with documentation.

---

## 11. New Files Summary

| File | Phase | Purpose |
|------|-------|---------|
| `bootstrap.ps1` | 1 | PowerShell bootstrap script |
| `installer/components/service_windows.py` | 3 | Task Scheduler integration |
| `hooks/bash_gate.py` | 4 | Cross-platform hook: bash gating |
| `hooks/spawn_guard.py` | 4 | Cross-platform hook: spawn guarding |
| `hooks/state_sanitize.py` | 4 | Cross-platform hook: state sanitization |
| `hooks/audit_log.py` | 4 | Cross-platform hook: audit logging |
| `hooks/canary_check.py` | 4 | Cross-platform hook: canary checking |
| `docs/getting-started/windows.md` | 5 | Windows quick start guide |
| `tests/unit/test_windows_paths.py` | 1 | Windows path resolution tests |
| `tests/unit/test_windows_symlinks.py` | 2 | Windows symlink fallback tests |
| `tests/unit/test_windows_service.py` | 3 | Windows service management tests |

## 12. Files Requiring Modification

| File | Phase | Changes |
|------|-------|---------|
| `installer/config.py` | 1 | OS-aware path resolution |
| `install.py` | 1 | Windows dependency handling, path defaults |
| `installer/components/symlinks.py` | 2 | Symlink fallback chain |
| `installer/components/mcp.py` | 3 | Task Scheduler + tasklist/taskkill |
| `installer/platforms/claude_code.py` | 2 | Use link abstraction |
| `installer/platforms/opencode.py` | 2 | Use link abstraction |
| `installer/platforms/codex.py` | 2 | Use link abstraction |
| `installer/platforms/gemini.py` | 2 | Use link abstraction |
| `installer/platforms/crush.py` | 2 | Use link abstraction |
| `installer/core.py` | 3 | Windows uninstall logic |
| `spellbook_mcp/terminal_utils.py` | 3 | Windows terminal detection |
| `.github/workflows/test.yml` | 1 | Add windows-latest to matrix |
| `README.md` | 5 | Windows installation instructions |
| `AGENTS.spellbook.md` | 5 | Note Windows support |
| `.gitattributes` | 1 | Enforce LF for shell scripts |
