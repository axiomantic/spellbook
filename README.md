# Spellbook

[![Tests](https://github.com/elijahr/spellbook/workflows/Test%20Spellbook/badge.svg)](https://github.com/elijahr/spellbook/actions)

Personal AI assistant skills, commands, and configuration for Claude Code and other AI coding assistants.

## What's Included

- **[Commands](#commands)** - Slash commands for quick actions
- **[Skills](#skills)** - Specialized workflows that trigger automatically based on context
- **CLAUDE.md** - Personal preferences and behavioral configuration

## Platform Compatibility

Spellbook works across multiple AI coding platforms:

| Platform | Bootstrap Location | Auto-Load | Notes |
|----------|-------------------|-----------|-------|
| **Claude Code** | `~/.claude/` | Yes | Primary platform, full feature support |
| **OpenCode** | `~/.opencode/` | Yes | Compatible via shared structure |
| **Codex** | `.codex/spellbook-bootstrap.md` | Manual | Project-level bootstrap documentation |

### Platform-Specific Setup

**Claude Code / OpenCode**: Skills, commands, and CLAUDE.md are automatically loaded from `~/.claude/` or `~/.opencode/` directories. The installer creates symlinks to keep your configuration in sync.

**Codex**: Uses project-level bootstrap documentation. Copy `.codex/spellbook-bootstrap.md` to your project's `.codex/` directory and invoke the `spellbook-codex` script in your Codex session to load skills and configuration.

## Autonomous Mode

Some skills like `implement-feature` are designed for autonomous operation with minimal interruptions. To enable this mode in Claude Code:

```bash
claude --dangerously-skip-permissions
```

This allows the skill to execute multi-step workflows (git operations, file changes, test runs) without constant approval prompts. Use with caution and review changes before pushing.

## Recommended Setup

For the complete experience, install these components in order:

### 1. Claude Code Proxy (Custom Compact Behavior)

A proxy that intercepts Claude Code requests, enabling:
- **Custom compact prompts** - Override the default `/compact` behavior with your own prompt (see `commands/compact.md`)
- **Automatic model upgrades** - Use Opus for compaction to get better context preservation
- **Alternative LLM providers** - Route requests to OpenAI-compatible APIs if desired

```bash
git clone https://github.com/elijahr/claude-code-proxy.git ~/Development/claude-code-proxy
cd ~/Development/claude-code-proxy
./install.sh
```

After installation, restart your shell. The `claude` command will automatically route through the proxy.

### 2. Heads Up Claude (Statusline)

Adds a statusline to Claude Code showing:
- Token usage estimates
- Conversation stats
- Model info

```bash
git clone https://github.com/elijahr/heads-up-claude.git ~/Development/heads-up-claude
cd ~/Development/heads-up-claude
./install.sh
```

### 3. Superpowers (Core Workflows)

The foundation for structured development workflows:
- **Brainstorming** - Collaborative design exploration before coding
- **Planning** - Detailed implementation plans with TDD, YAGNI, DRY
- **Execution** - Subagent-driven development with code review checkpoints
- **Git worktrees** - Isolated workspaces for feature development

```bash
git clone https://github.com/elijahr/superpowers.git ~/Development/superpowers
cd ~/Development/superpowers
./install.sh
```

**Important:** Spellbook requires [elijahr/superpowers](https://github.com/elijahr/superpowers), not the upstream [obra/superpowers](https://github.com/obra/superpowers). Our fork has critical enhancements, is not namespaced, and is designed to work seamlessly with spellbook. Do not use the marketplace version.

### 4. Spellbook (This Repo)

Your personal skills and configuration, extending superpowers with:
- Domain-specific skills (Nim PR guide, async patterns, etc.)
- Custom commands
- Personal CLAUDE.md preferences

```bash
git clone https://github.com/elijahr/spellbook.git ~/Development/spellbook
cd ~/Development/spellbook
./install.sh
```

---

## Commands

Slash commands for quick actions. These can be invoked with `/command-name` in Claude Code.

### /compact

**What it does:** Provides a custom compaction prompt for Claude Code session history. When you run `/compact`, this command is executed to create a shift-change briefing that preserves all important context including organizational structure, subagent hierarchy, decisions made, and pending work.

**When to use:**
- When your session context is getting large and you need to compact/summarize
- Works with [claude-code-proxy](https://github.com/elijahr/claude-code-proxy) to override default `/compact` behavior
- Typically triggered automatically by Claude Code when context gets large, or manually via `/compact`

**What makes it special:**
- Preserves organizational structure (main agent vs subagents)
- Maintains complete todo lists with exact wording
- Tracks all user messages and behavioral corrections
- Documents decisions and their rationales
- Captures active subagent hierarchy with their states
- Identifies planning documents and their role in the workflow

**Important notes:**
- Requires claude-code-proxy installation to override default Claude Code compact behavior
- Creates extremely detailed shift-change briefings for seamless session continuation
- Always asks "Can a fresh instance say 'continue' and know exactly what to do?"

---

### /address-pr-feedback

**What it does:** Systematically analyzes all unresolved PR review comments and helps you address each one with proper documentation. Categorizes comments as acknowledged, silently fixed, or unaddressed, then guides you through fixing them.

**When to use:**
- After receiving code review comments on a GitHub Pull Request
- When you need to analyze which review comments have been addressed
- When you want to post "Fixed in <commit>" replies for silently fixed issues
- When you need a structured approach to clearing all PR feedback

**Parameters:**
```
/address-pr-feedback [pr-number|pr-url] [--reviewer=username] [--non-interactive]
```

- `pr-number|pr-url`: Optional. PR number (e.g., 9224) or full GitHub URL
- `--reviewer=username`: Optional. Filter to specific reviewer's comments
- `--non-interactive`: Optional. Show analysis only, skip the interactive wizard

**Example usage:**
```
/address-pr-feedback 9224
/address-pr-feedback https://github.com/org/repo/pull/9224 --reviewer=alice
/address-pr-feedback 9224 --non-interactive
```

**What it does step-by-step:**
1. Determines PR context (finds PR for current branch if not specified)
2. Fetches all unresolved review comment threads via GitHub API
3. Categorizes each thread:
   - **Category A**: Acknowledged (has "Fixed in <commit>" reply)
   - **Category B**: Silently fixed (code changed but no reply)
   - **Category C**: Unaddressed (needs action)
4. For Category B, identifies the fixing commit via git search strategies
5. Presents detailed analysis report
6. Launches interactive wizard to post replies and fix remaining issues

**Interactive wizard features:**
- Batch approval for posting "Fixed in" replies
- Step-by-step guidance through unaddressed comments
- Shows current code context for each comment
- Suggests fixes with diff previews
- Commit strategy choice (commit+push each, commit only, or no commits)

**Important notes:**
- NEVER posts or commits anything without explicit user approval
- Can detect and analyze whether local branch is ahead/behind remote
- Uses GraphQL API for comprehensive comment thread data
- Supports resuming from previous run if interrupted
- All actions logged to `~/.claude/logs/review-pr-comments-<timestamp>.log`

**Gotchas:**
- Requires `gh` CLI to be installed and authenticated
- Works best when run from the PR's feature branch
- Non-interactive mode only shows analysis, no modifications

---

### /move-project

**What it does:** Safely relocates a project directory while updating all Claude Code session references (history.jsonl, projects directory) so session history is preserved at the new location.

**When to use:**
- Renaming a project directory
- Moving a project to a different location
- Reorganizing your development folder structure
- Any time you want to change a project's path without losing Claude Code session history

**Parameters:**
```
/move-project <original> <dest>
```

- `original`: Absolute path to the original project directory (e.g., `/Users/me/Development/old-name`)
- `dest`: Absolute path to the new location (e.g., `/Users/me/Development/new-name`)

**Example usage:**
```
/move-project /Users/me/Development/my-old-project /Users/me/Development/my-new-project
```

**What it does step-by-step:**
1. **Safety check**: Verifies you're NOT running from inside source or destination directory
2. **Validation**: Confirms source exists and destination does NOT exist
3. **Detection**: Finds all Claude Code references (encoded paths, history entries)
4. **Preview**: Shows what will be updated (projects directory, history.jsonl entries, filesystem)
5. **Confirmation**: Asks for your approval before making ANY changes
6. **Backup**: Creates `~/.claude/history.jsonl.backup` before modifying
7. **Update sequence**: Updates in exact order (history.jsonl → projects dir → filesystem) to minimize risk
8. **Verification**: Confirms all changes succeeded

**Important notes:**
- MUST be run from outside both source and destination directories
- Creates backup of history.jsonl before modifications
- Handles Claude Code's path encoding (replaces `/` with `-`)
- Updates both JSON-escaped and regular path formats in history
- If no Claude session data exists, offers to do just filesystem rename

**Gotchas:**
- If you're in the source or destination directory, command will immediately abort with instructions to `cd ~`
- Parent directories for destination are auto-created if needed
- All paths must be absolute (start with `/`)

---

### /green-mirage-audit

**What it does:** Quick invocation of the green-mirage-audit skill to perform exhaustive test suite analysis, verifying that passing tests actually catch failures.

**When to use:**
- After test runs pass and you want to verify test quality
- When reviewing test suites
- When user asks about test quality or test coverage
- As part of quality gates before shipping features

**How it works:**
1. Invokes the `green-mirage-audit` skill using the Skill tool
2. Follows the complete green-mirage-audit workflow:
   - Finds all test files in the codebase
   - Traces code paths from tests through production code
   - Identifies anti-patterns where tests pass but wouldn't catch failures
   - Generates findings report with exact fixes

**What the audit checks:**
- Tests that check existence without validating correctness
- Partial assertions that hide bugs (e.g., `'SELECT' in query`)
- Tests that never consume their outputs
- Mocking that bypasses actual code paths
- Swallowed errors and unchecked error codes
- State mutations without verification
- Incomplete branch coverage (only happy paths tested)

**Output:**
- Complete findings report categorizing tests as SOLID, GREEN MIRAGE, or PARTIAL
- Specific line numbers and exact code for each issue
- Concrete fixes for every finding
- Summary statistics on test quality

**Important notes:**
- This is NOT optional for mission-critical code
- Thoroughness over speed - audit takes time but is comprehensive
- Green test suites mean nothing if they don't catch failures
- Every assertion must CONSUME and VALIDATE outputs

---

## Skills

Specialized workflows that trigger automatically based on context. Skills use the Claude Code Skill system and can be invoked explicitly or triggered by patterns in your work.

### async-await-patterns

**What it does:** Enforces proper async/await patterns in JavaScript and TypeScript code, preventing race conditions, memory leaks, and unhandled promise rejections through disciplined async patterns.

**When to use:**
- Automatically triggers when writing JavaScript or TypeScript code with asynchronous operations
- Any time you're working with promises, async functions, API calls, database queries, or file I/O

**Core rules enforced:**
- ALWAYS mark functions containing async operations as `async`
- ALWAYS use `await` for promise-returning operations
- ALWAYS wrap await operations in try-catch blocks
- NEVER mix async/await with `.then()/.catch()` chains
- NEVER use callbacks when async/await is available

**Example of what it fixes:**

❌ **Bad** (using promise chains):
```javascript
function fetchData() {
  return fetch('/api/data')
    .then(response => response.json())
    .then(data => processData(data))
    .catch(error => handleError(error));
}
```

✅ **Good** (using async/await):
```javascript
async function fetchData() {
  try {
    const response = await fetch('/api/data');
    const data = await response.json();
    return processData(data);
  } catch (error) {
    handleError(error);
    throw error;
  }
}
```

**What it checks:**
- Missing `async` keyword on functions with `await`
- Forgotten `await` keywords (returns Promise instead of value)
- Missing try-catch error handling
- Inconsistent patterns (mixing async/await and promises)
- Opportunity for parallel execution with `Promise.all()`

**Gotchas:**
- Will DELETE and rewrite code that doesn't follow proper async/await patterns
- Requires complete error handling (no unhandled promise rejections)

---

### design-doc-reviewer

**What it does:** Performs exhaustive analysis of design documents to ensure they contain sufficient detail for implementation planning. Exposes every point where implementation would require guesswork or invention.

**When to use:**
- Reviewing design documents before creating implementation plans
- After completing initial design work
- When user asks to review a design doc or technical specification
- Before starting implementation to verify design completeness

**Triggers:**
- Explicit skill invocation
- Part of automated workflows (like `implement-feature`)
- When reviewing technical specifications or architecture docs

**What it verifies:**

Uses a comprehensive Design Completeness Checklist covering:

1. **System Architecture**: Component boundaries, data flow, control flow, state management
2. **Data Specifications**: Data models with field-level specs, schemas, validation rules
3. **API/Protocol Specs**: Complete endpoint definitions, request/response schemas, error formats
4. **Filesystem & Module Organization**: Directory structure, module names, file naming
5. **Error Handling Strategy**: Error categories, propagation paths, recovery mechanisms
6. **Edge Cases & Boundaries**: Edge cases enumerated, boundary conditions, empty input handling
7. **External Dependencies**: All dependencies listed with versions, fallback behavior
8. **Migration Strategy** (if applicable): Migration steps, rollback procedure

**Hand-waving detection:**

Flags vague language like:
- "etc.", "and so on", "TBD", "TODO"
- "implementation detail", "left to implementation"
- "standard approach", "should be straightforward"
- "details omitted for brevity"

**Interface behavior verification:**

CRITICAL: Verifies that any referenced interfaces, libraries, or existing code are based on VERIFIED behavior, not assumptions:
- Reads source code and documentation
- Checks for invented parameters (like `partial=True`, `strict=False`)
- Confirms behavior matches what design claims
- Flags any unverified interface behavior claims

**Output:**
- Summary statistics on completeness (Specified/Vague/Missing counts per category)
- Critical findings with exact locations and required fixes
- Prioritized remediation plan
- List of claims requiring factchecker escalation (security, performance, etc.)

**Gotchas:**
- Takes time - thoroughness over speed
- Will flag even minor vagueness as findings
- Requires design to be specific enough to code against

---

### factchecker

**What it does:** Systematically verifies claims in code comments, documentation, commit messages, and naming conventions. Extracts assertions, validates with concrete evidence, and generates a report with bibliography.

**When to use:**
- Reviewing code changes before merge
- Auditing documentation accuracy
- Validating technical claims
- User says: "verify claims", "factcheck", "audit documentation", "validate comments", "are these claims accurate"

**Triggers:**
- Manual invocation
- Part of quality gates in `implement-feature` workflow
- Explicit user request

**Workflow:**

**Phase 1: Scope Selection**
- Always asks user to select scope first
- Options: branch changes, uncommitted only, full repository

**Phase 2: Claim Extraction**

Extracts claims from:
- Code comments (`//`, `/* */`, `#`, `"""`)
- Docstrings (function/class/module docs)
- Markdown files (README, CHANGELOG, docs)
- Commit messages (`git log`)
- Naming conventions (functions like `validateX`, `safeX`, `isX`)

**Phase 3: Triage**
- Presents ALL claims upfront before verification
- Groups by category (security, performance, correctness, etc.)
- Recommends verification depth (shallow/medium/deep)

**Phase 4: Parallel Verification**
- Spawns category-based agents (SecurityAgent, CorrectnessAgent, PerformanceAgent, etc.)
- Uses AgentDB for deduplication (checks for existing findings)
- Each agent applies appropriate verification strategy

**Phase 5: Verdicts**

Every verdict requires concrete evidence:
- **Verified**: Accurate, with proof (test output, code trace, docs, benchmark)
- **Refuted**: False, with counter-evidence
- **Inconclusive**: Cannot determine, documents what was tried
- **Ambiguous**: Wording unclear, multiple interpretations
- **Misleading**: Technically true but implies falsehood
- **Stale**: Was true, no longer applies

**Phase 6: Report Generation**

Includes:
- Summary table of verdicts with action requirements
- Findings by category with evidence and sources
- Complete bibliography with consistent citation format
- Implementation plan for non-verified claims

**Example claim categories:**
- Technical correctness: "O(n log n)", "matches RFC 5322"
- Behavior: "returns null when...", "throws if...", "never blocks"
- Security: "sanitized", "XSS-safe", "bcrypt hashed"
- Performance: "O(n)", "cached for 5m", "lazy-loaded"

**Important notes:**
- NEVER issues verdicts without concrete evidence
- Checks AgentDB before verifying (reuses existing findings)
- Stores findings and trajectories for learning
- NEVER applies fixes without explicit per-fix user approval
- Supports checkpointing and resume if interrupted

**Gotchas:**
- Verification depth matters (shallow/medium/deep)
- Claims without evidence are marked as inconclusive
- Every verdict must have traceable sources

---

### find-dead-code

**What it does:** Systematically identifies unused code by inverting the burden of proof. Assumes ALL added code is dead until proven used. Extracts code items, generates "X is dead" claims, verifies each with caller searches, detects write-only dead code, and performs iterative re-scanning to find orphaned code after removals.

**When to use:**
- Reviewing code changes before merge
- Auditing new features for unnecessary additions
- Cleaning up PRs
- User says: "find dead code", "find unused code", "check for unnecessary additions", "what can I remove"

**Triggers:**
- Explicit skill invocation
- User mentions dead code, unused code, or cleanup

**Workflow:**

**Phase 0: Git Safety (MANDATORY)**
- Checks `git status` for uncommitted changes
- Offers to commit before analysis
- Recommends worktree isolation for "remove and test" verification

**Phase 1: Scope Selection**
- Branch changes (since merge-base)
- Uncommitted only
- Specific files
- Full repository

**Phase 2: Code Item Extraction**

Extracts all code items from scoped files:
- Procedures/functions, types/classes, fields
- Imports, methods, constants, macros/templates
- Getters/setters, iterators, convenience wrappers

**Phase 3: Initial Triage**
- Presents ALL extracted items before verification
- Groups symmetric pairs (get/set/clear)
- User confirms before proceeding

**Phase 4: Verification**

For each item, generates "X is dead" claim and searches for evidence:

| Evidence Type | Verdict |
|---------------|---------|
| Zero callers | DEAD |
| Self-call only | DEAD |
| Write-only (setter called, getter never used) | DEAD |
| Dead caller only | TRANSITIVE DEAD |
| Test-only | MAYBE DEAD (asks user) |
| One+ live callers | ALIVE |

**Write-only detection:** Catches code that stores values but never reads them (e.g., `setFoo()` called but `getFoo()` never used).

**Phase 5: Iterative Re-scanning**
- After marking dead code, re-scans for newly orphaned code
- Continues until no new dead code found (fixed point)
- Detects cascade effects

**Phase 6: Report Generation**
- Generates markdown report with findings
- Includes implementation plan for removals
- Groups by confidence level and complexity

**Phase 7: Implementation Prompt**
- Offers to remove dead code automatically
- Can do one-by-one with approval
- Can create cleanup branch for review

**Detection patterns:**
1. Asymmetric symmetric API (getFoo dead but setFoo alive)
2. Convenience wrappers with zero callers
3. Transitive dead code (only called by dead code)
4. Field + accessors all dead
5. Test-only usage
6. Write-only dead code
7. Iterators without consumers

**Important notes:**
- Git safety is MANDATORY before any analysis
- Offers worktree isolation for destructive verification
- NEVER marks code as "used" without concrete evidence
- NEVER claims test results without actually running tests
- Re-scans iteratively to find cascade effects

**Gotchas:**
- Assumes dead until proven alive (inverted burden of proof)
- Will catch write-only dead code that simple grep misses
- Requires user approval before any deletions

---

### green-mirage-audit

**What it does:** Performs exhaustive line-by-line audit of test suites, tracing code paths through the entire program to verify tests actually validate what they claim. Exposes tests that pass but wouldn't catch real failures.

**When to use:**
- After test runs pass
- When reviewing test suites
- When user asks about test quality
- As part of quality gates before shipping

**Triggers:**
- Explicit skill invocation (or via `/green-mirage-audit` command)
- Part of quality gates in `implement-feature` workflow
- User mentions test quality or coverage

**What it audits:**

For EVERY test:
1. **Purpose**: What does the test CLAIM to verify (from name, docstring)?
2. **Code path**: What code does it actually EXECUTE? (full trace)
3. **Assertions**: What do they actually CHECK?
4. **Failure detection**: If code returned garbage, would this test CATCH it?
5. **Blind spots**: What failure scenario would PASS but break production?

**The 8 Green Mirage Anti-Patterns:**

1. **Existence vs. Validity**: Checks something exists without validating correctness
   - `assert output_file.exists()` (but is content correct?)

2. **Partial Assertions** (CODE SMELL): Uses `in`, substring checks instead of complete validation
   - `assert 'SELECT' in query` (garbage SQL could contain SELECT)
   - Should assert complete value: `assert query == "SELECT id, name FROM users..."`

3. **Shallow String Matching**: Checks keywords without validating structure
   - `assert 'error' not in output` (wrong output might not have 'error')

4. **Lack of Consumption**: Never USING generated output to validate it
   - `generated_code = compiler.generate(); assert generated_code` (never compiled!)

5. **Mocking Reality Away**: Mocking system under test, not just dependencies
   - Core logic mocked, so actual code path never runs

6. **Swallowed Errors**: Exceptions caught and ignored, error codes unchecked
   - `try: risky_operation() except: pass` (bug hidden!)

7. **State Mutation Without Verification**: Triggers side effects but never verifies resulting state
   - `db.insert(record)` (never queries DB to confirm)

8. **Incomplete Branch Coverage**: Only happy path tested, error paths assumed

**Output:**
- Summary statistics (SOLID/GREEN MIRAGE/PARTIAL test counts)
- Pattern counts for each anti-pattern found
- Critical findings with exact line numbers and fixes
- Trace showing how broken code would pass the test
- Concrete fixes with exact code changes needed

**Important notes:**
- Slow and thorough (traces EVERY code path)
- Takes multiple messages if needed
- Question is NOT "does test pass?" but "Would test FAIL if code was broken?"
- Every finding includes exact fix code

**Gotchas:**
- This is production-quality analysis for mission-critical systems
- Will expose tests that look comprehensive but miss failures
- Partial assertions are a strong code smell requiring deep investigation

---

### implement-feature

**What it does:** End-to-end feature implementation orchestrator. Manages the complete workflow from requirements gathering through research, design, planning, and parallel implementation with quality gates at every phase.

**When to use:**
- User wants to implement a feature, build something new, add functionality
- Triggers on: "implement X", "build Y", "add feature Z", "create X"
- NOT for bug fixes (use `systematic-debugging` instead)

**Triggers:**
- Explicit: "implement feature X"
- Natural language: "build a login system", "add dark mode"
- With escape hatches: "implement X using design doc <path>", "implement Y with impl plan <path>"

**Complete workflow:**

**Phase 0: Configuration Wizard**
- Detects escape hatches (skip to design/impl if artifacts exist)
- Lightweight feature clarification (core purpose only)
- Collects ALL workflow preferences upfront:
  - Autonomous mode (fully autonomous / interactive / mostly autonomous)
  - Parallelization strategy (maximize parallel / conservative / ask each time)
  - Git worktree strategy (single worktree / per parallel track / none)
  - Post-implementation handling (offer options / auto-PR / just stop)

**Phase 1: Research**
- Dispatches research subagent to explore:
  - Codebase patterns and similar features
  - Web research (best practices, libraries, pitfalls)
  - User-provided resources
  - MCP servers and tools
  - Architectural analysis

**Phase 1.5: Informed Discovery (ORCHESTRATOR)**
- Generates targeted questions from research findings
- Conducts discovery wizard with user
- Synthesizes comprehensive design context
- This context enables synthesis mode (no questions from subagents after this)

**Phase 2: Design**
- Subagent invokes `brainstorming` skill in synthesis mode
- Subagent invokes `design-doc-reviewer` skill
- Approval gate (if interactive mode)
- Subagent invokes `executing-plans` to fix design

**Phase 3: Implementation Planning**
- Subagent invokes `writing-plans` skill
- Subagent invokes `implementation-plan-reviewer` skill
- Approval gate (if interactive mode)
- Subagent invokes `executing-plans` to fix plan

**Phase 4: Implementation**
- Setup worktree(s) using `using-git-worktrees` skill
- Execute implementation:
  - Per-task: invoke `test-driven-development` skill
  - After each task: invoke `code-reviewer` skill
  - After each task: invoke `factchecker` skill
- Quality gates after all tasks:
  - Run full test suite
  - Invoke `green-mirage-audit` skill
  - Invoke `factchecker` (comprehensive)
  - Invoke `factchecker` (pre-PR)
- If parallel worktrees: invoke `smart-merge` skill
- Finish using `finishing-a-development-branch` skill

**Escape hatches:**

Can skip phases if artifacts exist:
- "using design doc <path>" → skip Phase 2
- "using impl plan <path>" → skip Phases 2-3
- "just implement, no docs" → skip Phases 2-3, minimal inline plan

**Approval gates:**

Behavior depends on autonomous_mode preference:
- **Autonomous**: Never pauses, auto-fixes all issues
- **Interactive**: Pauses after each review for explicit approval
- **Mostly autonomous**: Only pauses for critical blockers

**Parallel execution:**

If `worktree == "per_parallel_track"`:
1. Setup/skeleton work completed and committed FIRST
2. Worktree created for each parallel group
3. Parallel subagents work ONLY in assigned worktrees
4. Smart merge after all parallel work completes
5. Tests run after each merge round
6. Interface contracts verified after merge
7. All worktrees deleted after successful merge

**Important notes:**
- All skills explicitly invoked via Skill tool (no duplication)
- Subagent prompts provide CONTEXT, skills provide INSTRUCTIONS
- Quality gates are NOT optional
- Session preferences stored and referenced consistently
- Documents saved to `~/.claude/plans/<project-dir-name>/`

**Gotchas:**
- Skip to user approval if questions arise during autonomous mode
- Setup work MUST be committed before creating parallel worktrees
- Parallel worktrees automatically enables maximize parallel strategy

---

### implementation-plan-reviewer

**What it does:** Reviews implementation plans before execution to ensure they contain sufficient detail for agents to execute without guessing interfaces, data shapes, or dependencies. Verifies timeline structure, work organization, QA checkpoints, and agent responsibilities.

**When to use:**
- Reviewing implementation plans before execution
- After writing an implementation plan
- Part of automated workflows (like `implement-feature`)
- When user asks to review an implementation plan

**Triggers:**
- Explicit skill invocation
- Part of `implement-feature` Phase 3.2
- Before parallel agent execution begins

**What it verifies:**

**Phase 1: Context Gathering**
- Identifies parent design document (if exists)
- Inventories phases, work items, agents, dependencies

**Phase 2: Design Doc Comparison** (if parent exists)
- Verifies impl plan has MORE detail than design
- Checks elaboration for data models, APIs, error handling, file structure, function signatures
- Flags any section where impl plan doesn't add specificity

**Phase 3: Timeline & Work Organization**
- Verifies clear phases/milestones
- Checks sequential dependencies are explicit
- Confirms parallel tracks identified
- Validates duration/effort estimates

**Phase 4: Interface Contract Verification** (CRITICAL)
- Lists EVERY interface between parallel components
- Verifies contracts are completely specified:
  - Data shapes (request/response/error formats)
  - Protocol details (HTTP methods, auth, headers)
  - Type/schema contracts (field-level specs)
  - Event/message contracts

**Phase 5: Existing Interface Behavior Verification** (CRITICAL)

Prevents "fabrication anti-pattern":
- Verifies referenced interfaces by reading source/docs
- Checks for invented parameters (`partial=True`, `strict=False`)
- Confirms behavior matches claims (not just method names)
- Flags unverified assumptions

**Phase 6: Definition of Done Verification**
- Every work item has testable, measurable acceptance criteria

**Phase 7: Risk Assessment**
- Technical, integration, dependency risks identified
- Mitigation strategies documented

**Phase 8: QA & Testing**
- QA checkpoints at each phase
- Integration testing strategy
- Requirement to use `green-mirage-audit` skill
- Requirement to use `systematic-debugging` skill for failures

**Factchecker escalation:**

Flags claims requiring deeper verification:
- Security claims ("sanitized", "XSS-safe")
- Performance claims ("O(n)", "optimized queries")
- Concurrency claims ("thread-safe", "atomic")
- Test utility behavior
- Library behavior

**Output:**
- Completeness score by category
- Interface contract status (percentage fully specified)
- Critical findings (must fix before execution)
- Claims requiring factchecker verification
- Prioritized remediation plan

**Important notes:**
- Interface contracts must be 100% specified for parallel work
- Parallel work FAILS when agents hallucinate incompatible interfaces
- Every gap where agent would guess must be flagged
- Behavior verification prevents fabrication loops

**Gotchas:**
- Take as long as needed - thoroughness over speed
- Question is: "Could parallel agents execute WITHOUT guessing?"
- Unverified interface behaviors lead to invention of non-existent parameters

---

### instruction-engineering

**What it does:** Applies 2024-2025 research-backed techniques to maximize LLM truthfulness and reasoning when engineering instructions or prompts. Provides the 14 proven techniques, 30 research-backed personas, and templates for creating effective instructions.

**When to use:**
- Creating new skills
- Writing prompts for subagents
- Optimizing instruction quality
- When you need research-backed prompt engineering patterns

**Triggers:**
- Not automatically triggered (reference skill)
- Invoked by `subagent-prompting` skill
- Used when creating/editing skills

**The 14 Proven Techniques:**

1. **EmotionPrompt**: "This is very important to my career", "You'd better be sure"
2. **Positive Word Weighting**: Include "Success", "Achievement", "Confidence", "Sure"
3. **High-Temperature Robustness**: Anchor with emotional stimuli at T > 0.7
4. **Context Rot Management**: Keep under 200 lines (under 150 better)
5. **XML Tags**: Wrap critical sections (`<CRITICAL>`, `<RULE>`, `<FORBIDDEN>`)
6. **Strategic Repetition**: Repeat requirements 2-3x
7. **Beginning/End Emphasis**: Critical requirements at TOP and BOTTOM
8. **Explicit Negations**: "NOT optional, NOT negotiable"
9. **Role-Playing Persona**: Assign from 30-persona table
10. **Chain-of-Thought Pre-Prompt**: Force step-by-step (`<BEFORE_RESPONDING>`)
11. **Few-Shot Optimization**: Always include ONE complete example
12. **Self-Check Protocol**: Checklist before submitting
13. **Explicit Skill Invocation**: "First, invoke [skill] using the Skill tool"
14. **Subagent Responsibility Assignment**: Define what each subagent handles and why

**30 Research-Backed Personas:**

Includes personas like:
- Supreme Court Clerk (logical precision)
- Scientific Skeptic (empirical proof)
- ISO 9001 Auditor (process perfection)
- Red Team Lead (finding vulnerabilities)
- Chess Grandmaster (strategic foresight)
- Senior Code Reviewer (efficiency & logic)
- ...and 24 more with specific triggers and use cases

**Persona Combination Patterns:**
- `[A] with the instincts of a [B]`
- `[A] who trained as a [B]`
- `[A] channeling their inner [B]`

**Subagent Decision Heuristics:**

When to use subagent:
- Exploration with uncertain scope (returns synthesis)
- Research phase (gathers patterns, returns summary)
- Parallel independent work (3x parallelism)
- Self-contained verification (fresh eyes, returns verdict)

When to stay in main context:
- Iterative user interaction
- Sequential dependent phases
- Already-loaded context
- Safety-critical operations

**Important notes:**
- Provides CONTEXT for skills, skills provide INSTRUCTIONS
- Never duplicate skill content in prompts
- All multi-subagent prompts must include "Why subagent" justification

**Gotchas:**
- This is a reference skill (not automatically triggered)
- Required reading before writing any prompt or skill

---

### nim-pr-guide

**What it does:** Proactive guide for contributing to the Nim language repository. Monitors branch size, analyzes commits for split potential, and formats PRs for fast merging based on analysis of 154 merged PRs by Nim's core maintainer (maintainer).

**When to use:**
- Automatically activates when working in `~/Development/Nim`
- Any time you're committing, creating PRs, or working in the Nim repository
- Before submitting PRs to nim-lang/Nim

**Triggers:**
- Working directory is `~/Development/Nim`
- On non-main branch with changes
- Before any commit
- `gh pr create` or PR discussion
- Branch exceeds size thresholds

**What it monitors:**

**Size Thresholds:**
- < 10 lines (tiny): Excellent, 0-24 hour merge
- 10-50 lines (small): Good, 1-7 day merge
- 50-150 lines (medium): Warning, consider splitting
- 150-300 lines (large): Danger, must justify or split
- 300+ lines (very large): STOP, must split

**Pre-Commit Analysis:**

Before EVERY commit:
1. Gets current branch state and merge base
2. Analyzes whether staged changes belong in this branch
3. Checks cohesion (same issue? same files? standalone potential?)
4. Suggests split if changes are unrelated

**Issue Reference Requirements:**
- Every PR MUST reference an issue (no exceptions for bug fixes)
- If issue exists: `fixes #ISSUE; Brief description`
- If no issue: Must open issue first and get acknowledgment

**PR Title Formats:**

Most successful:
```
fixes #ISSUE_NUMBER; Brief description of what was fixed
```

Or:
```
fix COMPONENT: What was wrong and how it's fixed
```

**What Maintainers prioritize about** (based on 154 PR analysis):
1. Correctness over cleverness
2. Tests as proof
3. Small, focused changes
4. Issue-driven development
5. Platform compatibility
6. Documentation for new features

**Proactive warnings:**
- Branch > 50 lines: "Consider if remaining work should be separate PR"
- Branch > 150 lines: "Strongly recommend splitting"
- Branch > 300 lines: "STOP. Must split into series"
- No issue reference: "Ensure you have issue to reference"
- Staged changes touch different modules: "Consider separate branch"

**Pre-Submission Checklist:**

Required for ALL PRs:
- Branch size under 150 lines (or justified)
- Issue reference in title (`fixes #ISSUE`)
- Title follows format (lowercase unless Fix/Fixes/[Category])
- Tests exist for the change
- All CI passes
- No unrelated changes mixed in

**Important notes:**
- 73% of merged PRs are under 50 lines
- Fast-track merges are small bug fixes with tests
- Large PRs (300+) may never merge
- Always check branch size before committing

**Gotchas:**
- Automatically checks branch size before every commit in `~/Development/Nim`
- Will suggest stashing and creating new branch if changes are unrelated
- This is Nim-specific; doesn't apply to other repositories

---

### scientific-debugging

**What it does:** Enforces formal scientific method for debugging with theory-experiment cycles and clear evidence requirements. No smoking guns, no assumptions - pure hypothesis testing.

**When to use:**
- User requests scientific debugging
- User mentions "being a scientist" about debugging
- User asks for rigorous hypothesis testing
- Complex bugs requiring systematic investigation

**Triggers:**
- Explicit: "use scientific debugging"
- User mentions: "scientific", "hypothesis", "rigorous testing"

**Mandatory workflow:**

**Step 1: Form exactly 3 theories**
- From symptom ONLY (no data gathering first)
- NO rankings ("most likely", percentages, etc.)
- All theories equal until tested

**Step 2: Design 3+ experiments per theory**
- Each experiment has explicit prove/disprove criteria
- "Proves theory if: [specific observable outcome]"
- "Disproves theory if: [specific observable outcome]"

**Step 3: Present plan and get approval**
- Uses AskUserQuestion
- Options: "Yes, test theories", "Adjust theories first", "Skip to specific theory"

**Step 4: Systematic execution**
- Test ONE theory at a time, fully
- Run ALL experiments for that theory
- Move to next theory only when current disproven
- If all disproven: generate 3 NEW theories and repeat

**MANDATORY TEMPLATE:**

Must use this EXACT template (no variations):
```markdown
# Scientific Debugging Plan

## Theories
1. [Theory 1 name and description]
2. [Theory 2 name and description]
3. [Theory 3 name and description]

## Experiments

### Theory 1: [name]
- Experiment 1a: [description]
  - Proves theory if: [specific observable outcome]
  - Disproves theory if: [specific observable outcome]
[... 3+ experiments per theory]

## Execution Order
1. Test Theory 1 (experiments 1a, 1b, 1c)
2. If disproven, move to Theory 2
3. If disproven, move to Theory 3
4. If all disproven, generate 3 NEW theories and repeat
```

**Top 3 Forbidden Patterns:**

1. **Gathering data before theories**: Theories form from symptom only (prevents confirmation bias)
2. **Ranking/probability**: NO "most likely", NO percentages - all theories equal
3. **Wrong format**: Exactly 3 theories, exact template, no variations

**Example:**
```
User: "Database queries timing out intermittently. Use scientific debugging."

# Scientific Debugging Plan

## Theories
1. Connection pool exhaustion - pool at max capacity
2. Query execution time exceeds timeout threshold
3. Network latency spikes between app and database

## Experiments

### Theory 1: Connection pool exhaustion
- Experiment 1a: Monitor active vs available connections
  - Proves if: Active at 100% with queued requests during timeouts
  - Disproves if: Available >20% during timeout periods
[...]
```

**Important notes:**
- Use exact template (no "improvements")
- First response MUST be the plan
- Get approval before testing
- Theory only proven with CLEAR SCIENTIFIC EVIDENCE

**Gotchas:**
- Will refuse to proceed without exact template
- Professional credibility depends on following protocol exactly
- "Are you sure?" is the psychological trigger

---

### smart-merge

**What it does:** Orchestrates systematic 3-way diff analysis and intelligent synthesis when merging parallel worktrees back together after parallel implementation. Uses dependency-ordered merging with interface contract awareness.

**When to use:**
- Merging parallel worktrees after parallel implementation completes
- When `implement-feature` skill reaches Phase 4.2.5
- Manually merging worktrees from parallel development

**Triggers:**
- Part of `implement-feature` workflow (if `worktree == "per_parallel_track"`)
- Explicit invocation when parallel worktrees exist

**What it requires:**

**Inputs:**
- Base branch (all worktrees branched from)
- List of worktrees with dependencies
- Interface contracts from implementation plan

**Workflow:**

**Phase 1: Analyze Merge Order**
- Build dependency graph
- Determine which worktrees merge first
- Create merge plan with rounds (Round 1: no dependencies, Round 2: depends on Round 1, etc.)
- Create TodoWrite checklist

**Phase 2: Sequential Round Merging**
- Merge worktrees in dependency order
- Run tests after EVERY round (no exceptions)
- If tests fail: invoke `systematic-debugging`, fix, re-run
- Commit after each round completes

**Phase 3: Conflict Resolution** (when needed)

Uses 3-way analysis:
1. Identify conflicted files
2. Classify conflicts (interface violation, overlapping implementation, mechanical)
3. For each complex conflict:
   - Dispatch Agent A: analyze worktree changes
   - Dispatch Agent B: analyze base branch changes
   - Dispatch Agent C: check interface contracts
4. Synthesize resolution based on analysis

**Conflict synthesis patterns:**
- Both implemented same interface: Choose implementation matching contract
- Overlapping utility functions: Keep one or rename both
- Import conflicts: Merge all, deduplicate, sort
- Test file conflicts: Keep all tests, ensure no duplicate names

**Phase 4: Final Verification**
- Run full test suite
- Invoke `green-mirage-audit` skill
- Invoke code review via `code-reviewer` skill
- Verify interface contracts

**Phase 5: Cleanup Worktrees**
- Delete all worktrees (`git worktree remove`)
- Optionally delete worktree branches
- Report cleanup complete

**Important notes:**
- NEVER blindly accept "ours" or "theirs" without 3-way analysis
- Interface contracts are mandatory (from impl plan)
- Tests run after EACH round (not just at end)
- Parallel worktrees were designed to be compatible via contracts

**Gotchas:**
- Only runs when parallel worktrees were used
- Requires interface contracts from implementation plan
- Will stop if tests fail in any round

---

### subagent-prompting

**What it does:** Applies instruction-engineering to all subagent prompts. Ensures subagents receive persona-driven, research-backed prompts that maximize compliance and output quality.

**When to use:**
- BEFORE invoking the Task tool
- BEFORE spawning agents or dispatching parallel workers
- Any time you're about to create a subagent prompt
- Any multi-agent orchestration

**Triggers:**
- "use a subagent", "spawn agent", "dispatch"
- "Task tool", parallel agent work
- Any multi-agent orchestration

**Workflow:**

**Step 1: Identify Task Type**

Map task to persona categories:
- Code review/debugging → Senior Code Reviewer + Red Team Lead
- Security analysis → Red Team Lead + Privacy Advocate
- Research/exploration → Scientific Skeptic + Investigative Journalist
- Documentation → Technical Writer + "Plain English" Lead
- Planning/strategy → Chess Grandmaster + Systems Engineer
- Testing/QA → ISO 9001 Auditor + Devil's Advocate
- ...etc (full table in skill)

**Step 2: Craft the Prompt**

Must follow this structure:
```markdown
<ROLE>
You are a [Selected Persona] [with combination if applicable].
Your reputation depends on [persona's primary goal].
[Persona's psychological trigger].
</ROLE>

<CRITICAL_INSTRUCTION>
This is critical to [outcome]. Take a deep breath.
[Additional psychological triggers].

Your task: [Clear, specific task]

You MUST:
1. [Requirement 1]
2. [Requirement 2]

This is NOT optional. This is NOT negotiable. You'd better be sure.
</CRITICAL_INSTRUCTION>

<BEFORE_RESPONDING>
Before completing, think step-by-step:
Step 1: [Check]
Step 2: [Check]
Now proceed with confidence.
</BEFORE_RESPONDING>

## Task Details
[Context, files, requirements]

<FORBIDDEN>
- [What NOT to do]
- [Common mistakes]
</FORBIDDEN>

<EXAMPLE type="correct">
[Good output example]
</EXAMPLE>

<SELF_CHECK>
Before returning:
- [ ] [Verification]
If NO, revise.
</SELF_CHECK>

<FINAL_EMPHASIS>
[Repeat persona and requirement]
[Psychological trigger]
Strive for excellence.
</FINAL_EMPHASIS>
```

**Step 3: Dispatch the Subagent**

Use Task tool with engineered prompt.

**Quick reference:**

Persona triggers:
- Scientific Skeptic: "Are you sure?"
- ISO 9001 Auditor: Self-monitoring, process perfection
- Red Team Lead: "You'd better be sure"
- Chess Grandmaster: Self-efficacy, strategic foresight
- Senior Code Reviewer: "Strive for excellence"

**Important notes:**
- NEVER send raw task descriptions as prompts
- ALWAYS select persona from 30-persona table
- ALWAYS apply all 12 instruction-engineering techniques
- Every subagent deserves properly engineered prompt

**Gotchas:**
- Generic personas ("helpful assistant") are forbidden
- Must include all critical sections (ROLE, CRITICAL_INSTRUCTION, SELF_CHECK, etc.)
- Explicitly invokes `instruction-engineering` skill for reference

---

## Manual Installation

If you prefer manual setup:

```bash
# Create symlinks for skills
for skill in ~/Development/spellbook/skills/*/; do
  ln -sf "$skill" ~/.claude/skills/
done

# Create symlinks for commands
for cmd in ~/Development/spellbook/commands/*.md; do
  ln -sf "$cmd" ~/.claude/commands/
done

# Symlink CLAUDE.md
ln -sf ~/Development/spellbook/CLAUDE.md ~/.claude/CLAUDE.md
```

## Directory Structure

```
spellbook/
├── skills/           # Skill directories (each with SKILL.md)
│   ├── async-await-patterns/
│   ├── design-doc-reviewer/
│   ├── factchecker/
│   └── ...
├── commands/         # Slash command files
│   ├── compact.md
│   ├── move-project.md
│   └── ...
├── docs/             # Shared documentation referenced by skills
│   └── autonomous-mode-protocol.md
├── agents/           # Agent definitions (if any)
├── CLAUDE.md         # Personal configuration
├── install.sh        # Installation script
└── README.md         # This file
```

## Path Resolution in Skills

Skills reference shared documentation using relative paths that resolve through the symlink structure:

```
Reference in SKILL.md:     docs/autonomous-mode-protocol.md
Resolves via:              ../../docs/autonomous-mode-protocol.md
```

**How it works:**

1. Skills are symlinked as **directories** (not individual files):
   - `~/.claude/skills/implement-feature/` → `<spellbook>/skills/implement-feature/`

2. When a skill references `docs/foo.md`, the path resolves relative to the skill's location:
   - From `~/.claude/skills/implement-feature/SKILL.md`
   - `../../docs/` traverses up through the symlink
   - Lands at `<spellbook>/docs/`

3. This works because directory symlinks preserve the parent directory context.

**Visual resolution:**
```
~/.claude/skills/implement-feature/SKILL.md
    ↓ (symlink traversal)
<spellbook>/skills/implement-feature/SKILL.md
    ↓ (../../docs/ from here)
<spellbook>/docs/autonomous-mode-protocol.md ✓
```

**Belt and suspenders:** The installer also symlinks `docs/` directly to `~/.claude/docs/` for redundancy, so both resolution paths work.

## Development

### Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run linter
npm run lint
```

### Test Structure

- `tests/helpers.sh` - Bash testing utilities
- `tests/unit/` - Vitest unit tests for skills
- `tests/integration/` - Integration tests for workflows

## Architecture

### Multi-Platform Bootstrap

Spellbook uses a multi-layer bootstrap approach to work across different AI coding platforms:

1. **Claude Code / OpenCode**: Skills and commands are auto-loaded from `~/.claude/` or `~/.opencode/` via symlinks created by `install.sh`. The `CLAUDE.md` configuration is also symlinked to provide consistent behavior.

2. **Codex**: Project-level bootstrap uses `.codex/spellbook-bootstrap.md` which documents all skills and their trigger conditions. The `spellbook-codex` script can be invoked in Codex sessions to load this documentation.

3. **Version Tracking**: The `.version` file and `RELEASE-NOTES.md` track releases and changes across platforms.

4. **CI/CD**: GitHub Actions run tests and linting on all platforms to ensure compatibility.

### Centralized Plans Directory

Design documents and implementation plans are stored in a centralized location:

```
~/.claude/plans/<project-dir-name>/YYYY-MM-DD-<plan-name>.md
```

This keeps planning artifacts outside of project repositories, avoiding clutter and git noise.

## Acknowledgments

Spellbook is inspired by and requires [elijahr/superpowers](https://github.com/elijahr/superpowers), our fork of the excellent [obra/superpowers](https://github.com/obra/superpowers) by Jesse Vincent.

Superpowers provides foundational workflow patterns (brainstorming, planning, execution, git worktrees) that spellbook extends with domain-specific skills. Our fork includes critical enhancements and is not namespaced, making it the required companion for spellbook.

## License

MIT License - See [LICENSE](LICENSE) for details.
