# Installation

## Quick Install (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash
```

The bootstrap script automatically:

1. Finds or installs Python 3.10+
2. Downloads and runs `install.py`
3. Installs uv (Python package manager) if missing
4. Installs git if missing
5. Clones spellbook to `~/.local/share/spellbook`
6. Installs skills for detected platforms

### Non-Interactive Install

For CI/CD or scripted installations:

```bash
curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash -s -- --yes
```

## install.py Reference

The installer is a self-bootstrapping Python script that handles all prerequisites automatically.

### Usage

```bash
# Via bootstrap (recommended)
curl -fsSL .../bootstrap.sh | bash

# Direct Python execution (requires Python 3.10+)
curl -fsSL .../install.py | python3

# From cloned repo
python3 install.py
uv run install.py
```

### Options

| Option | Description |
|--------|-------------|
| `--yes`, `-y` | Accept all defaults without prompting |
| `--install-dir DIR` | Install spellbook to DIR (default: `~/.local/share/spellbook`) |
| `--platforms LIST` | Comma-separated platforms: `claude_code,opencode,codex,gemini` |
| `--force` | Reinstall even if version matches |
| `--dry-run` | Show what would be done without making changes |
| `--verify-mcp` | Verify MCP server connectivity after installation |
| `--no-interactive` | Skip interactive platform selection UI |

### Examples

```bash
# Interactive install (shows platform selection UI)
python3 install.py

# Non-interactive with all defaults
python3 install.py --yes

# Install only Claude Code and Codex
python3 install.py --platforms claude_code,codex

# Preview what would be installed
python3 install.py --dry-run

# Force reinstall and verify MCP
python3 install.py --force --verify-mcp

# Custom install location
python3 install.py --install-dir ~/my-spellbook
```

### How It Works

The installer is designed to work in multiple scenarios:

**Curl-pipe execution** (`curl ... | python3`):

1. Detects it's running from stdin (no `__file__`)
2. Checks for uv, installs if missing
3. Checks for git, installs if missing
4. Clones repository to default location
5. Re-executes from cloned repo for full installation

**Repository execution** (`python3 install.py` from repo):

1. Detects spellbook repo from script location
2. Checks for uv, installs if missing
3. Re-executes under uv for Python version management
4. Runs platform installation

**Under uv** (`uv run install.py`):

1. PEP 723 metadata ensures correct Python version
2. Skips uv bootstrap (already running under uv)
3. Runs platform installation directly

### Platform Detection

The installer auto-detects available platforms by checking for their config directories:

| Platform | Config Directory | Always Available |
|----------|------------------|------------------|
| Claude Code | `~/.claude` | Yes (created if missing) |
| OpenCode | `~/.config/opencode` | No |
| Codex | `~/.codex` | No |
| Gemini CLI | `~/.gemini` | No |

In interactive mode, you can select which platforms to install. In non-interactive mode (`--yes` or piped input), all detected platforms are installed.

### What Gets Installed

For each platform, the installer:

1. **Skills** - Symlinks from `~/.claude/skills/` (or platform equivalent)
2. **Commands** - Symlinks from `~/.claude/commands/`
3. **Context files** - Updates CLAUDE.md/AGENTS.md with spellbook configuration
4. **MCP server** - Registers the spellbook MCP server for tool access

## Installation Modes

### Standard Install (Recommended)

The bootstrap script clones to `~/.local/share/spellbook`:

```bash
curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash
```

**Upgrade:**

```bash
cd ~/.local/share/spellbook
git pull
python3 install.py
```

### Development Install

For contributors or those who want the repo in a custom location:

```bash
# Clone to your preferred location
git clone https://github.com/axiomantic/spellbook.git ~/Development/spellbook

# Install from that location
cd ~/Development/spellbook
python3 install.py
```

The installer detects it's running from a spellbook repo and installs from there (no additional cloning). Symlinks point back to your development repo, so changes take effect immediately.

**Upgrade:**

```bash
cd ~/Development/spellbook
git pull
python3 install.py  # Re-run to update generated files, MCP registration, etc.
```

!!! note "Why re-run install.py after git pull?"
    Some files are generated or copied during installation (context files, MCP registration, etc.). Running `install.py` after pulling ensures everything stays in sync.

## Manual Prerequisites

If the bootstrap script can't install prerequisites automatically:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Python 3.10+ via uv (if needed)
uv python install 3.12

# Install git via your package manager
# macOS: xcode-select --install
# Ubuntu: sudo apt install git
```

## Uninstalling

```bash
python3 ~/.local/share/spellbook/uninstall.py
```

The uninstaller removes:

- Skill/command/agent symlinks
- Context file sections (CLAUDE.md, AGENTS.md)
- MCP server registration
- System services (launchd/systemd)

To also remove the repository:

```bash
rm -rf ~/.local/share/spellbook
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SPELLBOOK_DIR` | Auto-detected | Override spellbook source location |
| `SPELLBOOK_CONFIG_DIR` | `~/.local/spellbook` | Output directory for generated files |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Claude Code config directory |

!!! note "SPELLBOOK_DIR Auto-Detection"
    The installer and MCP server automatically find the spellbook directory by:

    1. Checking `SPELLBOOK_DIR` environment variable
    2. Walking up from the script location looking for `skills/` and `CLAUDE.spellbook.md`
    3. Defaulting to `~/.local/spellbook`

## Troubleshooting

### "Python not found"

The bootstrap script requires Python 3.10+. Install it via:

- **macOS:** `xcode-select --install` or `brew install python3`
- **Ubuntu/Debian:** `sudo apt install python3`
- **Fedora:** `sudo dnf install python3`

### "uv: command not found"

Restart your terminal or run:

```bash
source ~/.bashrc  # or ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"
```

### "git: command not found"

The installer will prompt to install git. Follow the OS-specific instructions, then re-run.

### Permission errors on Linux

Ensure target directories exist:

```bash
mkdir -p ~/.claude/{skills,commands,agents}
```

### MCP server not responding

Check if the daemon is running:

```bash
python3 ~/.local/share/spellbook/scripts/spellbook-server.py status
```

Restart if needed:

```bash
python3 ~/.local/share/spellbook/scripts/spellbook-server.py restart
```

## Companion Tools

### Heads Up Claude

Statusline showing token usage and conversation stats.

```bash
git clone https://github.com/axiomantic/heads-up-claude.git ~/Development/heads-up-claude
cd ~/Development/heads-up-claude && ./install.sh
```

### MCP Language Server

LSP integration for semantic code navigation.

```bash
git clone https://github.com/axiomantic/mcp-language-server.git ~/Development/mcp-language-server
cd ~/Development/mcp-language-server && go build
```

See `config/mcp-language-server-examples.json` for language-specific configurations.
