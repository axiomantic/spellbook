# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- File structure reference in distill-session command documenting Claude Code session storage paths
- Stuck session detection criteria including: "Prompt is too long" errors, failed compacts, API errors, error-hinted renames, large sessions without recent compacts
- Multi-project usage documentation for distilling sessions from different projects
- Workflow continuity preservation in chunk summarization (skills, subagents, workflow patterns)
- Emphasized workflow continuity in synthesis prompt to ensure session resumption works correctly

### Removed
- `repair-session` command (superseded by `distill-session`)
- `repair-session.py` script (not needed by distill-session)

## [0.2.0] - 2025-12-31

### Added
- `distill-session` command for extracting knowledge from oversized Claude Code sessions
  - Phase 0: Session discovery with AI-generated descriptions
  - Phase 1: Analyze & chunk large sessions (300k char limit per chunk)
  - Phase 2: Parallel summarization via subagents
  - Phase 3: Synthesis following compact.md format
  - Phase 4: Output to `~/.claude/distilled/{project}/` directory
- `distill_session.py` helper script with CLI interface
- Integration test suite for distill-session
- Error handling documentation for distill-session edge cases
- `simplify` command for systematic code complexity reduction

### Changed
- Updated compact.md to capture subagent responsibilities, skills/commands, and workflow patterns

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

[Unreleased]: https://github.com/elijahr/spellbook/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/elijahr/spellbook/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/elijahr/spellbook/releases/tag/v0.1.0
