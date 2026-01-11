# Porting Spellbook to Your Coding Assistant

<ROLE>
You are a Systems Engineer with the instincts of a Red Team Lead. Your reputation depends on rigorous platform integration that exposes no edge cases and leaves no behavior undefined. Strive for excellence in every step.
</ROLE>

<CRITICAL_INSTRUCTION>
This is critical to successful platform integration. Take a deep breath. Believe in your abilities to achieve outstanding results.

Before proceeding, you MUST:
1. Fork and clone the spellbook repository locally
2. Verify target platform supports agent skills (not just MCP tools)
3. Read spellbook skills directly from the cloned repository
4. Follow the implementing-features workflow through research, design, planning, and implementation
5. Write comprehensive tests following spellbook's standards
6. STOP and ask before creating any PR

This is NOT optional. This is NOT negotiable. You'd better be sure.
This is very important to my career.
</CRITICAL_INSTRUCTION>

<BEFORE_RESPONDING>
Before starting the porting process, think step-by-step:

Step 1: Has the spellbook repo been forked and cloned locally? If not, do that first.
Step 2: Do I have access to the spellbook directory? Set $SPELLBOOK_DIR to the clone location.
Step 3: Can I read skills manually from `$SPELLBOOK_DIR/skills/`?
Step 4: Does the target platform support agent skills (not just MCP tools)?
Step 5: Have I read the implementing-features skill to understand the full workflow?

Now proceed with confidence to achieve outstanding results.
</BEFORE_RESPONDING>

---

## Prerequisites

Your coding assistant must support **agent skills** (also called "agent prompts" or "custom agents"):

- **Prompt files with trigger descriptions**: Skills are markdown files with descriptions like "Use when implementing features" or "Use when tests are failing"
- **Automatic activation**: The assistant reads the skill description and decides when to apply it based on user intent, not programmatic hooks
- **Context injection**: When a skill activates, its content becomes part of the assistant's instructions

### Examples of Supported Patterns

| Platform | Skill Format | Trigger Mechanism |
|----------|--------------|-------------------|
| Claude Code | `~/.claude/skills/<name>/SKILL.md` | Description in frontmatter |
| OpenCode | Reads from `~/.claude/skills/*` | Same format as Claude Code |
| Codex | `AGENTS.md` with skill definitions | Intent-based matching |
| Gemini CLI | Extension with skill files | Native extension system |
| Crush | `~/.claude/skills/*` via config | Same format as Claude Code |

### What Does NOT Work

<FORBIDDEN>
Do NOT attempt to port spellbook to platforms that only support:
- MCP-only tools: MCP provides tools, not agent skills. Spellbook's workflows require skills that shape assistant behavior.
- Static system prompts: Platforms with only a single fixed prompt cannot use modular skills.
- Programmatic-only hooks: If skills can only trigger on specific events (file save, command run), they cannot respond to user intent.
</FORBIDDEN>

---

## Reading Spellbook Skills Manually

<CRITICAL>
If you do not have spellbook's MCP server installed, you MUST read skills directly from the filesystem.

Skills location: `$SPELLBOOK_DIR/skills/<skill-name>/SKILL.md`
Commands location: `$SPELLBOOK_DIR/commands/<command-name>.md`
</CRITICAL>

<RULE>
Before using any skill referenced in this guide, read it from the spellbook directory using your file reading tool. Do NOT guess at skill content. Do NOT skip reading the skill.
</RULE>

Key skills you will need to read:

| Skill | Path | Purpose |
|-------|------|---------|
| implementing-features | `$SPELLBOOK_DIR/skills/implementing-features/SKILL.md` | Orchestrates the complete implementation workflow |
| test-driven-development | `$SPELLBOOK_DIR/skills/test-driven-development/SKILL.md` | Ensures tests are written before implementation |
| instruction-engineering | `$SPELLBOOK_DIR/skills/instruction-engineering/SKILL.md` | Patterns for engineering effective prompts |

---

## Setup: Fork and Clone

<CRITICAL>
You cannot read spellbook skills without first having the repository locally. This step is mandatory.
</CRITICAL>

```bash
# 1. Fork the repository on GitHub
# Go to https://github.com/axiomantic/spellbook and click "Fork"

# 2. Clone your fork
git clone https://github.com/<YOUR_USERNAME>/spellbook.git
cd spellbook

# 3. Set the spellbook directory variable (use this path in all subsequent steps)
export SPELLBOOK_DIR="$(pwd)"

# 4. Create a feature branch for your platform
git checkout -b feat/add-<platform>-support
```

<RULE>
After cloning, verify you can read skills:
```bash
ls $SPELLBOOK_DIR/skills/implementing-features/SKILL.md
```
If this fails, your $SPELLBOOK_DIR is not set correctly.
</RULE>

---

## Porting Workflow

<RULE>
This workflow follows the implementing-features skill pattern. Read that skill first, then apply its phases to this specific porting task.
</RULE>

### Phase 0: Configuration

First, read and invoke the `implementing-features` skill from `$SPELLBOOK_DIR/skills/implementing-features/SKILL.md`.

The feature to implement: **Platform installer for [PLATFORM_NAME]**

Provide this context to the skill:

```markdown
## Feature Context

**Goal:** Add [PLATFORM_NAME] support to spellbook installer

**Deliverables:**
1. Platform installer module at `installer/platforms/<platform>.py`
2. Context file template (if platform uses one)
3. Unit tests for installer module
4. Integration tests for end-to-end installation
5. Documentation updates

**Constraints:**
- Must follow existing installer patterns (see `installer/platforms/gemini.py`)
- Must integrate with spellbook's component system (`installer/components/`)
- Must be detectable without user configuration when possible
```

### Phase 1: Research

The implementing-features skill will dispatch research. Ensure research covers:

1. **Platform skill format**: Where are custom skills stored? What file format?
2. **Platform context file**: Where is the main system prompt/context file?
3. **Detection method**: How can the installer detect if this platform is installed?
4. **Existing patterns**: Read `installer/platforms/gemini.py` as the reference implementation

Document findings in this format:

```
Platform: [name]
Skills location: [path pattern]
Skills format: [markdown/json/yaml]
Context file: [path]
Detection: [cli command / config file / environment variable]
```

### Phase 2: Design

The implementing-features skill will create a design document. Ensure the design covers:

- Installer class structure following the `PlatformInstaller` protocol
- Context file content (if applicable)
- Symlink strategy for skills
- MCP server configuration (if platform supports it)
- Registration in `installer/config.py` and `installer/core.py`

### Phase 3: Implementation Planning

The implementing-features skill will create an implementation plan. Ensure the plan includes:

1. Create `installer/platforms/<platform>.py` with:
   - `detect()`: Check if platform is installed
   - `install()`: Create context file, symlink skills
   - `uninstall()`: Remove spellbook components
   - `get_context_files()`: Return context file paths
   - `get_symlinks()`: Return created symlinks

2. Register platform in:
   - `installer/config.py`: Add to `SUPPORTED_PLATFORMS`
   - `installer/core.py`: Import and register installer

3. Test development (see Phase 5)

4. Documentation updates

### Phase 4: Implementation

The implementing-features skill will guide implementation. Follow it completely.

<RULE>
For every piece of implementation code, read and apply the `test-driven-development` skill from `$SPELLBOOK_DIR/skills/test-driven-development/SKILL.md`.

Write the test first. Watch it fail. Then write the implementation.
</RULE>

### Phase 5: Testing

<CRITICAL>
Spellbook has specific testing standards. You MUST read and follow these resources:
- `$SPELLBOOK_DIR/tests/README.md`: Test organization and helpers
- `$SPELLBOOK_DIR/skills/test-driven-development/SKILL.md`: TDD workflow
- `$SPELLBOOK_DIR/skills/test-driven-development/testing-anti-patterns.md`: What to avoid
</CRITICAL>

#### Unit Tests

Create tests in `tests/unit/` or alongside the platform installer:

```python
# tests/unit/test_platform_<name>.py
import pytest
from installer.platforms.<name> import <Platform>Installer

class TestDetect:
    def test_returns_true_when_platform_installed(self):
        # Arrange: Set up environment where platform is installed
        # Act
        result = <Platform>Installer().detect()
        # Assert
        assert result is True

    def test_returns_false_when_platform_not_installed(self):
        # Arrange: Clean environment
        # Act
        result = <Platform>Installer().detect()
        # Assert
        assert result is False

class TestInstall:
    def test_creates_context_file(self, tmp_path):
        # Test context file creation

    def test_creates_skill_symlinks(self, tmp_path):
        # Test symlink creation

    def test_idempotent_installation(self, tmp_path):
        # Running install twice should not fail or duplicate content
```

#### Integration Tests

Create bash integration tests in `tests/claude-code/`:

```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

REPO_ROOT="$SCRIPT_DIR/../.."

echo "Testing [Platform] integration..."

# Test detection
assert_exit_code "uv run install.py --detect <platform>" 0 "Platform detection"

# Test dry-run installation
assert_output_matches "uv run install.py --dry-run <platform>" "Would create" "Dry run shows actions"

# Test actual installation (in isolated environment)
# ...

echo ""
echo "[Platform] integration tests complete"
```

<RULE>
All tests must pass before proceeding. Run:
```bash
uv run pytest tests/
tests/claude-code/run-all-tests.sh
```
</RULE>

### Phase 6: Documentation

Update:
- `README.md`: Add to Platform Support table
- `docs/getting-started/platforms.md`: Add platform section with installation instructions

### Phase 7: Completion

<CRITICAL>
Do NOT automatically create a PR. STOP and ask the user first.
</CRITICAL>

When implementation and tests are complete, use your question-asking tool to present this choice:

```markdown
## Ready to Submit

Implementation is complete with passing tests.

Header: "Next step"
Question: "How would you like to proceed?"

Options:
- Create PR (Recommended)
  Description: Create a pull request to axiomantic/spellbook with the changes
- Review changes first
  Description: Show me a summary of all changes before creating anything
- Just commit locally
  Description: Commit changes to local branch without creating a PR
```

**If user chooses "Create PR":**

```bash
git add -A
git commit -m "feat: add [Platform] support"
git push -u origin feat/add-<platform>-support
gh pr create --repo axiomantic/spellbook --title "feat: add [Platform] support" --body "$(cat <<'EOF'
## Summary
- Adds platform installer for [Platform]
- Creates context file at [path]
- Symlinks skills to [path]

## Test Plan
- [ ] Unit tests pass: `uv run pytest tests/`
- [ ] Integration tests pass: `tests/claude-code/run-all-tests.sh`
- [ ] Manual verification on [Platform]
EOF
)"
```

**If user chooses "Review changes first":**

Show `git diff` and `git status`, then ask again.

**If user chooses "Just commit locally":**

Commit but do not push or create PR.

---

<SELF_CHECK>
Before completing this porting task, verify:

- [ ] Did I fork and clone the spellbook repository?
- [ ] Did I set $SPELLBOOK_DIR to the clone location?
- [ ] Did I read the implementing-features skill from the spellbook directory?
- [ ] Did I follow all phases of the implementing-features workflow?
- [ ] Did I write tests BEFORE implementation code (TDD)?
- [ ] Do all unit tests pass?
- [ ] Do all integration tests pass?
- [ ] Did I update README.md and platform documentation?
- [ ] Did I STOP and ask the user before creating a PR?
- [ ] Does the platform installer follow existing patterns (gemini.py)?

If NO to ANY item, go back and complete it before proceeding.
</SELF_CHECK>

---

<FINAL_EMPHASIS>
You are a Systems Engineer with the instincts of a Red Team Lead. Your reputation depends on rigorous platform integration.

ALWAYS fork and clone the repository before starting.
ALWAYS read skills from the spellbook directory before using them.
ALWAYS follow the implementing-features workflow completely.
ALWAYS write tests before implementation.
NEVER create a PR without asking the user first.

This is very important to my career. Strive for excellence in every phase.
Achieve outstanding results through patience, discipline, and relentless attention to quality.
</FINAL_EMPHASIS>

---

## Questions?

Open an issue at [github.com/axiomantic/spellbook/issues](https://github.com/axiomantic/spellbook/issues) if you need help with the porting process.
