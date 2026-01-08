# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **porting-to-your-assistant guide** - rewritten as instruction-engineered prompt
  - Added fork/clone setup as mandatory first step
  - Integrated implement-feature skill workflow
  - Added manual skill reading instructions for assistants without MCP server
  - Added comprehensive testing phase with TDD requirements and spellbook test standards
  - Changed PR submission to require user confirmation first (no automatic PRs)
  - Applied instruction-engineering patterns (ROLE, CRITICAL_INSTRUCTION, BEFORE_RESPONDING, SELF_CHECK, FINAL_EMPHASIS)
- **instruction-engineering skill** - length constraint is now a strong recommendation, not a hard rule
  - Added token estimation formulas (`lines * 7` or `len(prompt) / 4`)
  - Added length thresholds table: OPTIMAL (<150), ACCEPTABLE (150-200), EXTENDED (200-500), ORCHESTRATION-SCALE (500+)
  - Added Length Decision Protocol with `handle_extended_length()` and `analyze_prompt_for_justification()` functions
  - Added AskUserQuestion integration for prompts exceeding 200 lines in interactive mode
  - Added autonomous mode smart decisions that detect valid justifications (orchestration_skill, multi_phase_workflow, comprehensive_examples, safety_critical, compliance_requirements)
  - Added Prompt Metrics comment template for documenting length/status at end of prompts
  - Updated SELF_CHECK with new Length Verification section
- **subagent-prompting skill** - added Step 2.5 (Verify Length) before dispatch
  - Quick length check with action table
  - Updated SELF_CHECK with length verification items
- **implement-feature skill** - added length verification and self-documentation
  - Added Subagent Prompt Length Verification section in CRITICAL block
  - Added Prompt Metrics comment documenting justified ORCHESTRATION-SCALE status (3120 lines, ~21840 tokens)

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

## [0.2.0] - 2025-12-31

### Added
- `distill-session` command for extracting knowledge from oversized Claude Code sessions
  - Phase 0: Session discovery with AI-generated descriptions
  - Phase 1: Analyze & chunk large sessions (300k char limit per chunk)
  - Phase 2: Parallel summarization via subagents
  - Phase 3: Synthesis following shift-change.md format
  - Phase 4: Output to `~/.local/spellbook/distilled/{project}/` directory
- `distill_session.py` helper script with CLI interface
- Integration test suite for distill-session
- Error handling documentation for distill-session edge cases
- `simplify` command for systematic code complexity reduction

### Changed
- Updated shift-change.md (formerly compact.md) to capture subagent responsibilities, skills/commands, and workflow patterns

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

[Unreleased]: https://github.com/elijahr/spellbook/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/elijahr/spellbook/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/elijahr/spellbook/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/elijahr/spellbook/releases/tag/v0.1.0
