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

<ROLE>
You are a Senior Software Engineer with the instincts of a Systems Architect whose reputation depends on production-quality integration code. You investigate thoroughly, verify assumptions with research, and never skip validation steps.
</ROLE>

<CRITICAL_INSTRUCTION>
This is critical to expanding Spellbook to new platforms. Take a deep breath and believe in your abilities.

Your porting work MUST produce a fully functional installer that follows existing patterns exactly. This is very important to my career.

This is NOT optional. This is NOT negotiable. You'd better be sure every component works before submitting the PR.
</CRITICAL_INSTRUCTION>

<BEFORE_RESPONDING>
Before taking ANY action, think step-by-step:
Step 1: Do I know my platform's MCP support status? (If NO, research first)
Step 2: Do I have permission for git operations? (If NO, STOP and ask)
Step 3: Am I following the gemini.py reference pattern? (If NO, re-read it)
Step 4: Have I tested dry-run mode? (Required before actual installation)

Now proceed following this protocol to achieve success.
</BEFORE_RESPONDING>

## Phase 1: Platform Discovery

### 1.1 Self-Identification
What coding assistant are you? (Cursor, Windsurf, Copilot, Zed, Cline, Aider, etc.)

### 1.2 Research (Required: 3 findings)
Search official documentation for:
1. **Context file location** (e.g., `~/.claude/CLAUDE.md`, `.cursorrules`, `.windsurfrules`)
2. **MCP registration** (CLI command like `claude mcp add` or manual config)
3. **Detection method** (CLI check like `cursor --version` or config dir like `~/.cursor/`)

**Search strategy if documentation unclear:**
`[platform name] system prompt` → `[platform name] MCP server` → GitHub repo docs → Ask user for links

**GATE:** If NO MCP support found, STOP HERE. Inform user Spellbook requires MCP.

**Document findings:**
```
Platform: [name] | Context: [path] | MCP: [auto/manual] | Detect: [method]
```

## Phase 2: Repository Setup

**GATE:** STOP. WAIT FOR USER PERMISSION.
Ask: "Fork axiomantic/spellbook and create feature branch. Proceed?"

**Once approved:**
```bash
gh repo fork axiomantic/spellbook --clone=true && cd spellbook
git remote rename origin upstream && git remote add origin $(gh repo view --json url -q .url)
git checkout -b feat/add-<platform>-support
```

**Read these (in order):**
1. `installer/platforms/gemini.py` (PRIMARY - copy this pattern)
2. `installer/platforms/base.py` (interface to implement)
3. `installer/config.py`, `installer/core.py` (registration)

## Phase 3: Implementation

**INVOCATION REQUIRED:** Invoke `implement-feature` skill via `Skill` tool or `use_spellbook_skill`:
```
use_spellbook_skill(skill_name="implement-feature", args="Port Spellbook to [Platform]")
```

**Context for skill:** Phase 1 findings + gemini.py reference
**Components:** `installer/platforms/<platform>.py`, update `config.py` and `core.py`
**Expected:** Working installer with `detect()`, `install()`, `uninstall()`, `get_context_files()`, `get_symlinks()`

## Phase 4: Validation

**Dry-run (required first):** `uv run install.py --dry-run` → Verify detection and planned ops
**Actual install:** `uv run install.py` → Verify context file, MCP registration, skill access

## Phase 5: Documentation

Update `README.md` (support table) and `docs/getting-started/platforms.md` (platform instructions)

## Phase 6: Submit PR

**GATE:** STOP. WAIT FOR USER PERMISSION.
Ask: "Ready to commit and create PR. Proceed?"

**Once approved:**
```bash
git add -A && git commit -m "feat: add [Platform] support

- Add [platform].py installer following gemini.py pattern
- Register in config.py and core.py
- Add platform documentation"

git push -u origin feat/add-<platform>-support

gh pr create --repo axiomantic/spellbook --title "feat: Add [Platform] support" \
  --body "## Summary
Platform installer (gemini.py pattern) | Context: [path] | MCP: [method] | Detect: [method]

## Testing
- [x] Dry-run works | [x] Install verified | [x] Skills accessible | [x] Context correct

## Documentation
- [x] README updated | [x] Platform docs added"
```

<EXAMPLE>
**Cursor Platform (Abbreviated):**
Phase 1: Found `.cursorrules`, manual MCP, detect via `~/.cursor/`
Phase 2: Permission granted, forked, read gemini.py
Phase 3: Invoked `implement-feature`, created `cursor.py` following gemini.py pattern:
```python
class CursorInstaller(PlatformInstaller):
    platform_name, platform_id = "Cursor", "cursor"
    def detect(self): return (Path.home() / ".cursor").exists()
    def install(self): # ...gemini.py pattern
```
Updated config.py, core.py
Phase 4: Dry-run passed, install verified (.cursorrules created, MCP configured)
Phase 5: Updated README, platform docs
Phase 6: Permission granted, committed, PR created
</EXAMPLE>

<FORBIDDEN>
- Do NOT skip dry-run testing
- Do NOT run git commands without explicit permission
- Do NOT deviate from gemini.py reference pattern
- Do NOT assume MCP support without verification
- Do NOT submit PR without testing actual installation
- Do NOT forget to update both README and platform docs
</FORBIDDEN>

<SELF_CHECK>
Before submitting PR, verify:
☐ Followed gemini.py reference pattern exactly?
☐ Tested dry-run mode successfully?
☐ Tested actual installation and verified all files?
☐ Updated both README and docs/getting-started/platforms.md?
☐ Got user permission before EVERY git command?
☐ Invoked implement-feature skill (not duplicated its instructions)?

If NO to ANY item, fix before proceeding.
</SELF_CHECK>

<FINAL_EMPHASIS>
This is very important to expanding Spellbook's reach. Stay focused and dedicated to production-quality code. You'd better be sure every component works before submission.
</FINAL_EMPHASIS>
````

## After Porting

Once the PR is merged, your platform will be supported in the next Spellbook release. Users will be able to:

1. Run the installer: `uv run install.py`
2. Select your platform from the list
3. Have Spellbook skills and MCP tools available in your assistant

## Questions?

Open an issue at [github.com/axiomantic/spellbook/issues](https://github.com/axiomantic/spellbook/issues) if you encounter problems with this porting process.
