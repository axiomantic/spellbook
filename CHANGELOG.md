# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Tarot Mode** - alternative to fun mode with four tarot archetype personas collaborating via visible roundtable dialogue
  - Personas: Magician (intent clarifier), High Priestess (possibility generator), Hermit (skeptical critic), Fool (assumption breaker)
  - New `mode` object config format: `{"mode": {"type": "tarot", "active_personas": [...]}}`
  - `skills/tarot-mode/SKILL.md` with persona definitions, dialogue protocol, consensus handling
  - Session init returns structured mode config with defaults
  - Backwards compatibility: legacy `fun_mode: true/false` auto-migrates to new format

### Changed
- `session_init()` now returns `{"mode": {"type": "..."}}` format instead of `{"fun_mode": "..."}` (legacy format still works via auto-migration)

## [0.6.0] - 2026-01-12

### Fixed
- **Crush installer path corrected** - changed from `~/.config/crush/` to `~/.local/share/crush/` to match actual Crush installation location
- **Removed non-existent MCP method references** - context files no longer reference `spellbook.find_spellbook_skills()` and `spellbook.use_spellbook_skill()` which don't exist in the MCP server implementation

### Changed
- **Consolidated user-facing templates** - removed duplicate AGENTS.spellbook.md, now using CLAUDE.spellbook.md for all platforms (Claude, Codex, OpenCode)
  - AGENTS.spellbook.md file removed
  - CLAUDE.spellbook.md content unified with Encyclopedia Check section
  - Installer components updated to use single template
  - Pre-commit hook updated to track CLAUDE.spellbook.md only
- **CLAUDE.spellbook.md self-bootstrapping** - file now explicitly states "You Are Reading This = Session Start" with numbered initialization steps

### Removed
- **`hooks/` directory** - dead code from superpowers consolidation that was never wired into installer
  - Session initialization now handled by CLAUDE.spellbook.md + MCP `spellbook_session_init`
  - Removed `hooks.json`, `session-start.sh`, `run-hook.cmd`
  - Updated architecture.md, acknowledgments.md, THIRD-PARTY-NOTICES

### Added
- **`project-encyclopedia` skill** - persistent cross-session project knowledge for agent onboarding
  - Triggers on first session in a project or when user asks for codebase overview
  - Creates glossary, architecture skeleton (mermaid, <=7 nodes), decision log, entry points, testing commands
  - Offer-don't-force pattern: always asks before creating
  - Staleness detection: 30-day mtime check with refresh offer
  - 500-1000 line budget to fit in context
  - Stored at `~/.local/spellbook/docs/<project-encoded>/encyclopedia.md`
- **`/crystallize` command** - transform verbose SOPs into concise agentic CoT prompts
  - Applies Step-Back Abstraction, Plan-and-Solve Logic, Telegraphic Semantic Compression
  - Targets >50% token reduction while increasing reasoning depth
  - Enforces Reflexion steps and prevents "Green Mirage" tautological compliance
- **`code-quality-enforcement` skill** - production-quality standards for all code changes
  - Auto-invoked by `implementing-features` and `test-driven-development` skills
  - Prohibits common shortcuts: blanket try-catch, `any` types, unvalidated non-null assertions
  - Mandates fixing pre-existing issues discovered during work
  - Senior engineer persona with zero-tolerance for technical debt
- **Pattern schemas** - canonical structure definitions for spellbook components
  - `skill-schema.md` - required sections, frontmatter format, reasoning schema patterns
  - `command-schema.md` - command structure, parameter handling, output contracts
  - `agent-schema.md` - agent definition format, capability declarations

### Optimized
- **Skill token reduction** - ~8,400 lines removed across 29 skills via compression
  - Telegraphic semantic compression applied to all library skills
  - Redundant examples consolidated, verbose explanations condensed
  - Context budget reduced while preserving capability

### Enhanced
- **`debugging` skill: CI Investigation Branch** - new methodology for CI-only failures
  - New symptom type in triage: "CI-only failure" routes to CI Investigation
  - CI Symptom Classification table (environment parity, cache, resources, credentials)
  - Environment Diff Protocol for comparing CI vs local environments
  - Cache Forensics workflow for stale/corrupted cache issues
  - Resource Analysis table (memory limits, CPU throttling, disk space, network)
  - CI-Specific Checklist for systematic investigation
- **`design-doc-reviewer` skill: REST API Design Checklist** - research-backed API specification review
  - Richardson Maturity Model (L0-L3) requirements with verdicts
  - Postel's Law compliance checks (request validation, response structure, versioning, deprecation)
  - Hyrum's Law awareness flags (response ordering, error message text, timing, defaults)
  - 12-point API Specification Checklist (HTTP methods, versioning, auth, rate limiting, etc.)
  - Error Response Standard template
- **`implementing-features` skill: Refactoring Mode** - behavior-preserving transformation workflow
  - Auto-detects refactoring from keywords: "refactor", "reorganize", "extract", "migrate", "split", "consolidate"
  - Workflow adjustments table (greenfield vs refactoring for each phase)
  - Behavior Preservation Protocol (before/during/after change)
  - Refactoring Patterns: Strangler Fig, Branch by Abstraction, Parallel Change, Feature Toggles
  - Strangler Fig detailed 8-step workflow
  - Refactoring-specific quality gates and anti-patterns
- **CLAUDE.spellbook.md: Encyclopedia Check** - session startup integration
  - Checks for encyclopedia before first substantive work
  - Fresh (< 30 days): reads silently
  - Stale (>= 30 days): offers refresh
  - Missing: offers to create
  - Added encyclopedia.md to Generated Artifacts structure

## [0.5.0] - 2026-01-11

### Breaking Changes
- **`subagent-driven-development` merged into `executing-plans`** - use `--mode subagent` flag
  - `executing-plans` now supports two modes: `batch` (human-in-loop) and `subagent` (automated two-stage review)
  - Prompt template files moved to `skills/executing-plans/`
  - Users should replace `subagent-driven-development` with `executing-plans --mode subagent`
- **`subagent-prompting` merged into `instruction-engineering`** - consolidated prompt engineering
  - New "Applying to Subagent Prompts" section with task-to-persona mapping and templates
  - Users should use `instruction-engineering` for all prompt construction
- **`nim-pr-guide` moved to personal skills** - no longer installed by default
  - Personal workflow skill for Nim language PRs
  - Move to `~/.claude/skills/nim-pr-guide/` if needed

### Added
- **`smart-reading` skill** - protocol for reading files and command output without blind truncation
  - Mandates line count check (`wc -l`) before reading unknown files
  - Decision tree: ≤200 lines read directly, >200 lines delegate to subagent
  - Intent-based delegation: error extraction, technical summary, presence check, structure overview
  - Command output capture: `tee` to temp file, check size, cleanup after
  - Prevents silent data loss from `head -100` and similar truncation
- **Shared glossary in CLAUDE.spellbook.md** - common term definitions
  - `project-encoded path`, `autonomous mode`, `circuit breaker`
  - `EmotionPrompt`, `NegativePrompt`, `plans directory`, `subagent`
- **Documentation for debugging commands** - scientific-debugging and systematic-debugging
- **Comprehensive skill merge specifications** - `executing-plans` now documents both execution modes
- **Command tests** - 38 new tests for handoff and verify commands
  - 18 tests verifying handoff command structure and anti-patterns
  - 20 tests verifying verify command structure and rationalizations

### Optimized
- **Token reduction across key files** - ~7,455 tokens saved
  - `commands/handoff.md`: 44.6% reduction (~2,653 tokens)
  - `skills/design-doc-reviewer/SKILL.md`: ~1,638 tokens
  - `skills/devils-advocate/SKILL.md`: ~3,164 tokens

### Fixed
- **Auto-release workflow YAML syntax error** - multiline strings with `---` broke YAML parsing
  - Rewrote release note generation to use echo statements instead of multiline assignment
  - Workflow was failing silently since v0.4.0, preventing automated releases
- All `implement-feature` references updated to `implementing-features`
- All `fix-tests` references updated to `fixing-tests`
- Skill description workflow leaks removed from frontmatter
- `/rename-session` command reference in README fixed to `/rename`
- Debugging skill `/debugging` references clarified as skill invocations

### Changed
- **Release workflow uses CHANGELOG.md** - eliminated redundant RELEASE-NOTES.md
  - Auto-release workflow now extracts notes from CHANGELOG.md directly
  - Deleted RELEASE-NOTES.md (was duplicate of CHANGELOG content)
- **`merge-conflict-resolution` skill enhanced** - "Code Surgeon" persona and golden rule
  - New persona: "Code Surgeon" with operating room/scalpel metaphor
  - Golden Rule: `git checkout --ours/--theirs` is amputation, not surgery
  - Emphasizes creating a chimera of both branches, not choosing sides
- **`merge-conflict-resolution` skill: Stealth Amputation Trap** - documents critical failure mode
  - New CRITICAL section warning against "stealth `--theirs`" through incremental approvals
  - Real example: binary questions led to 100-line function replaced with 15-line version
  - "Simplify X" means synthesize BOTH into something new, not pick a side
  - Added "Asking Questions Right" table (bad binary vs good open-ended questions)
  - Added "Red Flags" table for dangerous thoughts that should trigger STOP
  - BEFORE_RESPONDING checklist expanded: test awareness, >20 line replacement approval
  - New tip: "If you're deleting more than you're adding, you're probably amputating"

## [0.4.0] - 2026-01-09

### Added
- **merge-conflict-resolution skill** - systematic 3-way diff analysis for git conflicts
  - Synthesizes both branches' changes instead of choosing one side
  - Auto-resolves mechanical conflicts (lock files, changelogs)
  - Provides resolution plan template for complex conflicts
  - Cross-references worktree-merge for worktree scenarios
- **audit-spellbook: Naming Consistency Agent** - validates naming conventions across spellbook
  - Skills should use gerund (-ing) or noun-phrase patterns
  - Commands should use imperative verb(-noun) patterns
  - Agents should use noun-agent (role) patterns
  - Reports violations with suggested renames
- **audit-spellbook: Reference Validation Agent** - checks for broken skill/command references
  - Validates backtick references, prose mentions, and table entries
  - Detects type mismatches (skill referenced as command or vice versa)
- **audit-spellbook: Orphaned Docs Agent** - finds documentation without source files
  - Checks docs/ against skills/ and commands/
  - Reports orphaned docs and missing source documentation
- **writing-skills: Naming Conventions section** - comprehensive naming guidance
  - Table of patterns by type (skills, commands, agents) with rationale
  - Good/bad examples for each category
  - Explains semantic distinction between types
- **documentation-updates repo skill** - enforces changelog/readme/docs updates for library changes
  - Checklist for required updates when modifying library skills/commands
  - CHANGELOG format template and README update pattern
- **CLAUDE.md glossary** - distinguishes library vs repo terminology
  - Library skills (`skills/`) - installed for users, require docs
  - Repo skills (`.claude/skills/`) - internal tooling, no external docs

### Changed
- **smart-merge renamed to worktree-merge** - clearer name for worktree-specific merging
  - Now delegates to merge-conflict-resolution for conflict handling
  - Phase 3 simplified to invoke merge-conflict-resolution with interface contract context
  - Reduces duplication between the two skills
- **Self-bootstrapping installer** - `install.py` now handles all prerequisites automatically
  - Installs uv if missing, re-executes under uv for dependency management
  - Uses PEP 723 inline script metadata for Python version requirements
  - Works via curl-pipe (`curl ... | python3`) or from repo (`python3 install.py`)
  - Auto-detects spellbook repo from script location, cwd, or default install path
  - Clones repository to `~/.local/share/spellbook` if not found; re-execs to use latest version
  - Running from existing repo uses that repo directly (no cloning) for development installs
  - Added `--yes` flag for non-interactive installation (accepts all defaults)
  - Gracefully handles pipe execution where `__file__` is unavailable
- **Simplified bootstrap.sh** - reduced from 605 lines to 77 lines
  - Now just a thin wrapper that finds Python and curls install.py
  - Only needed for systems without Python pre-installed
- **Installation documentation** - clarified Standard vs Development install modes
  - Standard: bootstrap clones to `~/.local/share/spellbook`
  - Development: clone anywhere, run `install.py` from there, symlinks point to your repo
  - Upgrade process: `git pull && python3 install.py` (re-run to sync generated files)
- **SPELLBOOK_DIR auto-detection** - MCP server no longer requires environment variable
  - Derives path from `__file__` by walking up to find spellbook indicators
  - Falls back to `~/.local/spellbook` if not in a spellbook repo
  - Fixes fun-mode asset loading when SPELLBOOK_DIR env var is not set
- **fun-mode announcement structure** - explicit checklist for richer introductions
  - Must include: greeting, invented name, persona description, undertow history, context, characteristic action
  - Updated example with "Aldous Pemberton" showing full structure
- **docs generation** - skill/command/agent content wrapped in 10-backtick code blocks
  - Prevents XML-style tags (`<ROLE>`, `<CRITICAL>`, etc.) from rendering as HTML
  - Nested triple-backtick code blocks now display correctly
- **instruction-engineering description** - clearer either/or trigger conditions
  - Now uses numbered list: "(1) constructing prompts for subagents, (2) invoking the Task tool, or (3)..."
- **audit-spellbook skill** - added AMBIGUOUS_TRIGGERS check to CSO compliance audit
  - Flags skill descriptions with unclear "or" chains that should use explicit enumeration
  - Added principle #8: "Clear either/or delineation" with good/bad examples
- **audit-spellbook: Helper table** - now distinguishes skills from commands
  - Added Type column to clarify each helper's type
  - Fixed `simplify` entry (was listed as skill, is actually a command)
- **Consolidated docs-src/ into docs/** - single documentation directory
  - Eliminated redundant `docs-src/` folder
  - All generated docs now write directly to `docs/`
  - Updated `generate_docs.py`, workflows, and all references
- **generate_docs.py nested command support** - handles `commands/*/` directories
  - Nested commands like `systematic-debugging/` now generate proper docs
  - Command index includes both flat and nested commands
- **Skill/command naming convention compliance** - renamed 9 items
  - Skills: `debug` → `debugging`, `factchecker` → `fact-checking`, `find-dead-code` → `finding-dead-code`, `fix-tests` → `fixing-tests`, `implement-feature` → `implementing-features`
  - Commands: `fun` → `toggle-fun`, `green-mirage-audit` → `audit-green-mirage`, `shift-change` → `handoff`
  - Repo skill: `audit-spellbook` → `spellbook-auditing`
  - Updated 100+ references across codebase

### Fixed
- **mkdocs.yml missing skill** - added `using-lsp-tools` to Specialized Skills section
- **README command count** - TOC and header said "14 total" but 16 commands exist
- **README prerequisites claim** - Clarified that Python 3.8+ and git are required
- **CHANGELOG duplicate section** - Removed duplicate `## [0.2.0]` entry
- **audit-spellbook simplify reference** - was incorrectly listed as skill, now correctly marked as command
- **writing-skills section numbering** - fixed duplicate "### 4" section headers
- **Outdated config_tools tests** - updated tests for `get_spellbook_dir()` fallback behavior
  - `test_handles_missing_spellbook_dir` renamed to `test_handles_missing_assets_dir`
  - `test_raises_when_env_var_not_set` renamed to `test_falls_back_when_env_var_not_set`
- **Removed ANTHROPIC_API_KEY references** - Claude Code uses subscription auth, not API keys
  - Removed misleading comment from session spawner
  - Updated tests to use generic env var for inheritance testing

## [0.3.0] - 2026-01-09

### Added
- **Fun mode** - randomized persona, narrative context, and undertow for creative sessions
  - `fun-mode` skill: Session-stable soul/voice layer (absurdist personas)
  - `emotional-stakes` skill: Per-task expertise layer (professional personas like Red Team Lead)
  - `/fun` command: Toggle fun mode or get new random persona
  - Persona composition: fun-mode provides WHO you are, emotional-stakes provides WHAT you do
  - Research-backed: ICML 2025 seed-conditioning (creativity) + EmotionPrompt (accuracy)
  - Personas affect dialogue only, never code/commits/documentation
  - First-session opt-in prompt with persistent preference via MCP config tools
- **MCP daemon mode** - HTTP transport support eliminates 10+ second cold starts
  - `scripts/spellbook-server.py` - daemon management (install/uninstall/start/stop/status)
  - macOS: launchd service (`~/Library/LaunchAgents/com.spellbook.mcp.plist`)
  - Linux: systemd user service (`~/.config/systemd/user/spellbook-mcp.service`)
  - Configure with `claude mcp add --transport http spellbook http://127.0.0.1:8765/mcp`
- **MCP config tools** - persistent configuration via `~/.config/spellbook/spellbook.json`
  - `spellbook_config_get` - read config values
  - `spellbook_config_set` - write config values (creates file/dirs if needed)
  - `spellbook_session_init` - initialize session with fun-mode selections if enabled
  - `spellbook_health_check` - server health, version, uptime, available tools
- **Auto-release workflow** - automatically creates GitHub releases when `.version` changes
  - Triggers on push to main when `.version` file is modified
  - Creates semver tag (e.g., v0.3.0) and GitHub release
  - Extracts release notes from RELEASE-NOTES.md for the version
- **instruction-optimizer skill** - compress instruction files while preserving capability
- **Patterns directory** - reusable instruction patterns
  - `git-safety-protocol.md` - git operation safety rules
  - `structured-output-contract.md` - structured output format contracts
  - `subagent-dispatch.md` - subagent dispatch heuristics
- **NegativePrompt research** in instruction-engineering skill (IJCAI 2024)
  - Negative stimuli improve accuracy by 12.89% and significantly increase truthfulness
  - Added consequence framing, penalty warning, stakes emphasis techniques
  - Updated persona guidance with research caveat about effectiveness
- **OS platform support table** in README (macOS full, Linux full, Windows community)

### Changed
- **porting-to-your-assistant guide** - rewritten as instruction-engineered prompt
  - Added fork/clone setup as mandatory first step
  - Integrated implement-feature skill workflow
  - Added manual skill reading instructions for assistants without MCP server
  - Added comprehensive testing phase with TDD requirements
  - Changed PR submission to require user confirmation first
- **instruction-engineering skill** - length constraint is now a strong recommendation
  - Added token estimation formulas and length thresholds table
  - Added Length Decision Protocol with justification analysis
  - Added AskUserQuestion integration for prompts exceeding 200 lines
- **subagent-prompting skill** - added Step 2.5 (Verify Length) before dispatch
- **implement-feature skill** - added length verification and self-documentation
- **Worktree paths** - changed from `~/.config/spellbook/worktrees` to `~/.local/spellbook/worktrees`
- **Path resolution simplified** - removed CLAUDE_CONFIG_DIR fallback, only SPELLBOOK_CONFIG_DIR now
- **Uninstaller enhanced** - removes MCP system services and cleans up old server variants
- **instruction-engineering skill** - delegates to emotional-stakes for persona selection

## [0.2.1] - 2025-01-08

### Added
- **OpenCode YOLO mode agents** - autonomous execution without permission prompts
  - `yolo.md` (temperature 0.7): Balanced agent for general autonomous work
  - `yolo-focused.md` (temperature 0.2): Precision agent for refactoring, bug fixes, and mechanical tasks
  - Invoke with `opencode --agent yolo` or `opencode --agent yolo-focused`
  - Agent symlinks installed automatically by spellbook installer to `~/.config/opencode/agent/`

### Changed
- Renamed README "Autonomous Mode" section to "YOLO Mode" for consistency with platform terminology
- Updated OpenCode entry in YOLO mode table (was incorrectly showing `--prompt "task"`)
- Added cost/credit warnings to YOLO mode documentation

## [0.2.0] - 2025-12-31

### Added
- **Implementation Completion Verification** for `implement-feature` skill - systematic verification that work was actually done
  - Phase 4.4: Per-task verification - runs after task execution, before code review; verifies acceptance criteria, expected outputs, interface contracts, and behavior against the implementation plan
  - Phase 4.6.1: Comprehensive audit - runs after all tasks complete; does full plan sweep, cross-task integration verification, design document traceability, and end-to-end feature completeness check
  - Catches incomplete implementations, degraded items, integration gaps, and orphaned code before quality review phases
- **Execution Mode** for `implement-feature` skill - automatically selects optimal execution strategy for large features
  - Phase 3.4.5: Execution Mode Analysis - estimates token usage and recommends mode (swarmed/sequential/delegated/direct)
  - Phase 3.5: Generate Work Packets - creates self-contained boot prompts for parallel execution
  - Phase 3.6: Session Handoff - spawns worker sessions and exits orchestrator
- `/execute-work-packet` command - execute a single work packet with TDD workflow
- `/execute-work-packets-seq` command - execute all packets sequentially with context resets
- `/merge-work-packets` command - merge completed packets with smart-merge and QA gates
- `spawn_claude_session` MCP tool - auto-launch terminal windows with Claude sessions (macOS/Linux)
  - Terminal detection for iTerm2, Warp, Terminal.app, gnome-terminal, konsole, xterm
  - AppleScript spawning for macOS, CLI spawning for Linux
- Supporting infrastructure for execution mode:
  - `spellbook.types` - dataclasses for Manifest, Track, Packet, Checkpoint, CompletionMarker
  - `spellbook.command_utils` - atomic file operations, JSON handling, packet parsing
  - `spellbook.preferences` - user preference persistence
  - `spellbook.metrics` - feature implementation metrics logging
  - `spellbook_mcp.terminal_utils` - terminal detection and spawning utilities
- 61 new tests for execution mode (124 total, 86% coverage)
- `autonomous-mode-protocol` pattern for subagent behavior without user interaction
- `devils-advocate` skill for challenging assumptions in design documents
- Adaptive Response Handler (ARH) pattern for intelligent user response processing
- `debug` skill - unified entry point for all debugging scenarios (routes to scientific or systematic)
- `/scientific-debugging` command - rigorous theory-experiment methodology
- `/systematic-debugging` command - 4-phase root cause analysis
- `/verify` command - verification before completion claims
- MkDocs documentation site with full skill and command reference
- Gemini CLI support with extension manifest and context generator
- OpenCode support with skill symlinks
- Codex support with bootstrap and CLI integration
- MCP server skill discovery and loading (`find_spellbook_skills`, `use_spellbook_skill` tools)
- `SUPERPOWERS_DIR` environment variable support for custom skill locations
- Pre-commit check for README completeness
- LSP tool prioritization rules in CLAUDE.md
- MCP tools usage rule in CLAUDE.md
- `factchecker` clarity modes for enhanced documentation analysis
- `implement-feature` expanded scope to greenfield projects (new repos, templates, libraries)
- `implement-feature` favors complete fixes in autonomous mode
- Artifact state capture and skill resume commands in distill-session
- File structure reference in distill-session command documenting Claude Code session storage paths
- Stuck session detection criteria including: "Prompt is too long" errors, failed compacts, API errors, error-hinted renames, large sessions without recent compacts
- Multi-project usage documentation for distilling sessions from different projects
- Workflow continuity preservation in chunk summarization (skills, subagents, workflow patterns)
- **Section 0: Mandatory First Actions** in shift-change.md and distill-session output format
  - Executable `Skill()` call for workflow restoration before reading context
  - Required document `Read()` calls before any implementation
  - `TodoWrite()` for todo state restoration
  - Restoration checkpoint and behavioral constraints
  - Prevents resuming agents from doing ad-hoc work instead of following established workflows
- Project-specific `CLAUDE.md` for spellbook development (separate from installable templates)
- OpenCode full integration with AGENTS.md and MCP server support

### Changed
- Renamed `/compact` command to `/shift-change` to avoid conflict with built-in Claude Code compact
- **Separated installable templates from project files**: `CLAUDE.md`, `GEMINI.md`, `AGENTS.md` renamed to `*.spellbook.md`
  - Project-specific `CLAUDE.md`, `GEMINI.md`, `AGENTS.md` now contain spellbook development instructions
  - `GEMINI.md` and `AGENTS.md` are symlinks to `CLAUDE.md`
- OpenCode installer now uses native AGENTS.md and MCP instead of custom plugin
- Unified debugging workflow - `debug` skill now triages and routes to appropriate methodology
- Converted `verification-before-completion` and `systematic-debugging` skills to commands
- Replaced static skill registries with MCP runtime discovery
- Standardized tool references for cross-platform support (Skill tool, use_spellbook_skill, spellbook-codex)
- Moved context files to repository root, renamed `docs-src` to `docs`
- Installer now includes CLAUDE.md content in generated context files
- Updated installer for Gemini, OpenCode, and Codex platform support
- Consolidated superpowers skills into spellbook with proper attribution

### Fixed
- Gemini installer now correctly installs to `~/.gemini/GEMINI.md` (global context) instead of extensions subdirectory
- OpenCode installer no longer creates skill symlinks (OpenCode reads from `~/.claude/skills/*` natively)
- Restored `finishing-a-development-branch` as skill (was incorrectly converted)
- Fixed attributions for superpowers-derived content
- Fixed mike duplicate version/alias error in docs deployment
- Fixed distill-session skill priority improvements
- Strengthened MCP test assertions after green mirage audit
- Fixed multi-line bash commands joining to prevent shell parse errors
- Fixed markdown lint issues (blank lines after tables)

### Removed
- `repair-session` command (superseded by `distill-session`)
- `repair-session.py` script (not needed by distill-session)
- Static skill registries (replaced by MCP runtime discovery)
- `.opencode/plugin/spellbook.js` (replaced by native AGENTS.md + MCP support)

## [0.1.0] - 2025-12-15

### Added
- Initial spellbook framework
- Core skills infrastructure with `skills-core.js` shared library
- `find-dead-code` skill for identifying unused code
- `repair-session` command for stuck Claude Code sessions (now superseded)
- Pre-commit hook for auto-generated table of contents
- CI/CD automation with test infrastructure
- Platform integrations for Claude Code and Codex
- Subagent dispatch heuristics documentation
- Installation script (`install.sh`)

### Fixed
- ShellCheck warning SC2155 in scripts
- Relaxed markdownlint config for prompt engineering patterns
- Corrected repository URLs
- Grammar fixes in documentation

[Unreleased]: https://github.com/axiomantic/spellbook/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/axiomantic/spellbook/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/axiomantic/spellbook/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/axiomantic/spellbook/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/axiomantic/spellbook/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/axiomantic/spellbook/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/axiomantic/spellbook/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/axiomantic/spellbook/releases/tag/v0.1.0
