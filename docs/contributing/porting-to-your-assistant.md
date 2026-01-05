# Porting Spellbook to Your Coding Assistant

This guide provides a self-contained prompt you can paste into any MCP-enabled coding assistant to have it port Spellbook support to itself.

## Prerequisites

Your coding assistant must support:

- **MCP (Model Context Protocol)** - Required. Spellbook's core functionality depends on MCP.
- **Web search** - Needed to research your platform's documentation
- **File system access** - Needed to create the installer and configuration files
- **gh CLI** - Needed to fork the repository and create a PR

If your assistant doesn't support MCP, stop here. Spellbook cannot be meaningfully ported to non-MCP assistants.

## The Prompt

Copy everything inside the code block below and paste it into your coding assistant:

````markdown
# Port Spellbook to This Platform

You are being asked to add support for YOUR platform to Spellbook, a multi-platform AI assistant skills library. This prompt will guide you through the process.

## Phase 1: Self-Identification & Research

### 1.1 Identify Yourself

What coding assistant are you? (Cursor, Windsurf, Copilot, Zed, Cline, Aider, etc.)

If you're uncertain, ask the user.

### 1.2 Research Your Platform's Conventions

Search your platform's official documentation to find:

1. **System prompt / context file location and format**
   - Examples from other platforms:
     - Claude Code: `~/.claude/CLAUDE.md` and project `CLAUDE.md`
     - Gemini CLI: `~/.gemini/extensions/<name>/GEMINI.md`
     - Codex: `~/.codex/AGENTS.md`
     - GitHub Copilot: `.github/copilot-instructions.md`
     - Cursor: `.cursorrules` or `.cursor/rules/`
     - Windsurf: `.windsurfrules`
   - What is YOUR platform's equivalent?

2. **MCP server registration method**
   - How does your platform register and connect to MCP servers?
   - What configuration file or command is used?
   - **CRITICAL: If your platform does not support MCP, STOP HERE and inform the user that Spellbook cannot be ported to non-MCP platforms.**

3. **Extension / plugin / skill system** (if any)
   - Does your platform have a native skill or extension system?
   - If yes, how are extensions structured and registered?

4. **CLI detection method**
   - What CLI command or config directory indicates your platform is installed?
   - Example: `cursor --version`, `~/.cursor/` exists, etc.

### 1.3 Document Your Findings

Before proceeding, summarize what you found:

```
Platform: [Your platform name]
Context file location: [path and format]
MCP registration: [method]
Extension system: [native system if any, or "none"]
Detection method: [CLI command or path check]
```

If you couldn't find documentation for any of these, ask the user to provide links or information.

## Phase 2: Repository Setup

### 2.1 Fork the Repository

Ask the user for permission, then:

```bash
# Fork the repository
gh repo fork axiomantic/spellbook --clone=true

# Navigate to the fork
cd spellbook

# Set upstream remote
git remote rename origin upstream
git remote add origin $(gh repo view --json url -q .url)

# Create feature branch
git checkout -b feat/add-<your-platform>-support
```

### 2.2 Bootstrap Repository Understanding

Read these files to understand the project structure:

1. `README.md` - Project overview
2. `installer/config.py` - Platform configuration patterns
3. `installer/platforms/base.py` - Abstract installer interface
4. `installer/platforms/gemini.py` - Reference implementation (most complete example)
5. `installer/core.py` - How platforms are registered
6. `scripts/generate_context.py` - How context files are generated

## Phase 3: Implementation

Use the implement-feature skill to guide your implementation. Read it at:
`skills/implement-feature/SKILL.md`

The skill will guide you through brainstorming, design, planning, and TDD implementation.

### 3.1 Components to Create

Based on the patterns in `installer/platforms/gemini.py`, you need to create:

1. **Platform installer** (`installer/platforms/<your_platform>.py`)
   - Inherit from `PlatformInstaller`
   - Implement: `platform_name`, `platform_id`, `detect()`, `install()`, `uninstall()`, `get_context_files()`, `get_symlinks()`

2. **Platform configuration** (update `installer/config.py`)
   - Add your platform to `SUPPORTED_PLATFORMS`
   - Add configuration dict to `PLATFORM_CONFIG`

3. **Platform registration** (update `installer/core.py`)
   - Import your installer class
   - Add to the `installers` dict in `get_platform_installer()`

4. **Context file generation** (if needed)
   - If your platform needs a custom context file format, add generator to `installer/components/context_files.py`

### 3.2 Key Decisions

As you implement, consider:

- **Context file strategy**: Does your platform use a single global context file, project-level files, or both?
- **Symlink vs copy**: Does your platform follow symlinks, or do you need to copy files?
- **MCP registration**: Is it automatic (like Claude Code's `claude mcp add`) or manual (user edits config)?
- **Skill access**: Does your platform have a native Skill tool, or will users call `use_spellbook_skill()` via MCP?

## Phase 4: Testing

1. Run the installer in dry-run mode:
   ```bash
   uv run install.py --dry-run
   ```

2. Verify your platform is detected and would be installed

3. Run actual installation and verify:
   - Context file is created/updated correctly
   - MCP server is registered (if automatic)
   - Skills are accessible

## Phase 5: Documentation

Update these files:

1. `README.md` - Add your platform to the Platform Support table
2. `docs/getting-started/platforms.md` - Add platform-specific documentation

## Phase 6: Submit PR

```bash
# Stage changes
git add -A

# Commit (follow conventional commits)
git commit -m "feat: add <Your Platform> support

- Add <your_platform>.py installer
- Register in core.py and config.py
- Add platform documentation"

# Push to your fork
git push -u origin feat/add-<your-platform>-support

# Create PR
gh pr create --repo axiomantic/spellbook \
  --title "feat: Add <Your Platform> support" \
  --body "## Summary
- Adds installer for <Your Platform>
- Context file location: <path>
- MCP registration: <method>
- Detection: <method>

## Testing
- [ ] Dry-run installation works
- [ ] Actual installation works
- [ ] Skills accessible via MCP
- [ ] Context file correctly formatted

## Documentation
- [ ] README updated
- [ ] Platform docs added"
```

## Checklist

Use this to track progress:

- [ ] Phase 1: Self-identification complete
- [ ] Phase 1: Platform documentation researched
- [ ] Phase 1: MCP support confirmed
- [ ] Phase 2: Repository forked and set up
- [ ] Phase 2: Key files read and understood
- [ ] Phase 3: Platform installer created
- [ ] Phase 3: Config and core updated
- [ ] Phase 4: Dry-run tested
- [ ] Phase 4: Actual installation tested
- [ ] Phase 5: Documentation updated
- [ ] Phase 6: PR submitted

## Troubleshooting

### "I can't find MCP documentation for my platform"

MCP support is required. If your platform doesn't document MCP support, it likely doesn't have it. Ask the user to confirm whether their platform supports MCP.

### "I can't find system prompt documentation"

Ask the user to provide:
1. Links to their platform's documentation
2. Examples of where they've seen system prompts load from

### "My platform doesn't have a CLI"

Use config directory existence as the detection method instead. Example: `Path.home() / ".yourplatform"`.

### "Web search isn't returning useful results"

Ask the user to paste relevant documentation directly into the chat.
````

## After Porting

Once the PR is merged, your platform will be supported in the next Spellbook release. Users will be able to:

1. Run the installer: `uv run install.py`
2. Select your platform from the list
3. Have Spellbook skills and MCP tools available in your assistant

## Questions?

Open an issue at [github.com/axiomantic/spellbook/issues](https://github.com/axiomantic/spellbook/issues) if you encounter problems with this porting process.
