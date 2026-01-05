# Installation

## Quick Install (Recommended)

The bootstrap script handles everything automatically, including installing prerequisites:

```bash
curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash
```

The script will:

1. **Check/install git** - Prompts to install Xcode CLT (macOS) or via package manager (Linux)
2. **Check/install uv** - Fast Python package manager from [Astral](https://docs.astral.sh/uv/)
3. **Check/install Python** - Uses uv to install Python 3.12 if no suitable version found
4. **Clone spellbook** - To `~/.local/share/spellbook`
5. **Run the installer** - Configure platforms interactively

### Bootstrap Options

```bash
# Interactive install (recommended)
curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash

# Non-interactive with defaults
curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash -s -- --yes

# Custom install location
curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash -s -- --install-dir ~/my-spellbook

# Specific platforms only
curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash -s -- --platforms claude_code,codex

# Show all options
curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash -s -- --help
```

### What Gets Installed

| Prerequisite | How | Notes |
|--------------|-----|-------|
| **git** | System package manager | Xcode CLT on macOS, apt/dnf/pacman on Linux |
| **uv** | Official installer | Fast Python package manager |
| **Python 3.10+** | Via uv | Standalone, doesn't affect system Python |

!!! note "Build Tools (Optional)"
    If you encounter build errors with Python packages, install development tools:

    - **macOS:** `xcode-select --install`
    - **Ubuntu/Debian:** `sudo apt install build-essential python3-dev`
    - **Fedora:** `sudo dnf groupinstall 'Development Tools'`

## Manual Installation

If you prefer to install prerequisites yourself:

### 1. Install uv

[uv](https://docs.astral.sh/uv/) is required for running spellbook scripts.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart your terminal or run:
```bash
source ~/.bashrc  # or ~/.zshrc
```

### 2. Install Python (if needed)

If you don't have Python 3.10+, uv can install it:

```bash
uv python install 3.12
```

### 3. Clone and Install

```bash
git clone https://github.com/axiomantic/spellbook.git ~/.local/share/spellbook
cd ~/.local/share/spellbook
uv run install.py
```

## Updating

```bash
cd ~/.local/share/spellbook
git pull
uv run install.py
```

Or re-run the bootstrap script:
```bash
curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash
```

## Uninstalling

```bash
uv run ~/.local/share/spellbook/uninstall.py
```

Or manually:
```bash
rm -rf ~/.claude/skills/* ~/.claude/commands/* ~/.claude/agents/*
rm -rf ~/.local/share/spellbook
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SPELLBOOK_DIR` | `~/.local/share/spellbook` | Override install location |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Claude Code config directory |

## Companion Tools

### Heads Up Claude (Recommended)

Statusline showing token usage and conversation stats.

```bash
git clone https://github.com/elijahr/heads-up-claude.git ~/Development/heads-up-claude
cd ~/Development/heads-up-claude
./install.sh
```

### MCP Language Server (Recommended)

LSP integration for semantic code navigation.

```bash
git clone https://github.com/axiomantic/mcp-language-server.git ~/Development/mcp-language-server
cd ~/Development/mcp-language-server
go build
```

See `config/mcp-language-server-examples.json` for language-specific configurations.

## Troubleshooting

### "uv: command not found"

Restart your terminal or run:
```bash
source ~/.bashrc  # or ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"
```

### "Python not found" after uv install

uv installs Python to its own managed location. Use `uv run` to execute scripts:
```bash
uv run install.py  # Not: python install.py
```

### Permission errors on Linux

If symlink creation fails, ensure the target directories exist:
```bash
mkdir -p ~/.claude/{skills,commands,agents}
```
