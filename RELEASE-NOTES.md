# Spellbook Release Notes

## 0.3.0 - 2026-01-08

### Added
- **Fun mode**: Randomized persona, narrative context, and undertow for more creative sessions
  - `fun-mode` skill adopts random persona/context/undertow, synthesizes into cohesive introduction
  - `/fun` command to toggle, customize, or disable fun mode
  - Research-backed: inspired by ICML 2025 seed-conditioning findings on LLM creativity
  - Personas affect dialogue only, never code/commits/documentation
- **Auto-release workflow**: Automatically creates GitHub releases when `.version` changes
  - Creates semver tag and GitHub release with notes from RELEASE-NOTES.md
  - Updates floating major version tag (e.g., v0)
- **README branding**: Tagline updated to "Also fun." with new "Serious Fun" section

## 0.2.1 - 2026-01-08

### Added
- **OpenCode YOLO mode agents**: Autonomous execution without permission prompts
  - `yolo.md` (temperature 0.7): Balanced agent for general autonomous work
  - `yolo-focused.md` (temperature 0.2): Precision agent for refactoring, bug fixes, mechanical tasks
  - Invoke with `opencode --agent yolo` or `opencode --agent yolo-focused`

### Changed
- Renamed README "Autonomous Mode" section to "YOLO Mode"
- Fixed OpenCode entry in YOLO mode table (was incorrectly showing `--prompt "task"`)
- Added cost/credit warnings to YOLO mode documentation

## 0.2.0 - 2026-01-06

### Added
- **Crush platform support**: Full integration with Charmbracelet's Crush CLI
- **Native skills for Gemini CLI**: Skills now load via native extension system instead of MCP-only
- **Native skills for Codex**: AGENTS.md bootstrap with proper skill definitions
- **Section 0 mandatory first actions**: Distilled sessions now include executable restoration commands at the top
- **Playbooks in README**: Real-world usage scenarios with example transcripts showing context exhaustion handling, session handoff, test auditing, and parallel worktree development

### Changed
- **Platform-specific installer architecture**: Refactored installer into separate platform modules (claude_code.py, gemini.py, opencode.py, codex.py, crush.py)
- **Renamed /compact to /shift-change**: Better reflects the purpose of custom session compaction
- **CLAUDE_CONFIG_DIR support**: distill-session command and script now properly respect the environment variable

### Fixed
- CI test runner no longer references non-existent test-codex-cli.sh
- RELEASE-NOTES.md version header now matches .version file
- README command links for /execute-work-packet, /execute-work-packets-seq, /merge-work-packets now render correctly

## 0.1.0 - 2025-12-30

### Added
- Multi-platform support (Claude Code, OpenCode, Codex)
- Version tracking with .version file and RELEASE-NOTES.md
- Test infrastructure with bash helpers and Vitest unit tests
- CI/CD with GitHub Actions (test and lint workflows)
- Comprehensive README documentation with platform compatibility
- Codex integration (.codex/spellbook-bootstrap.md, spellbook-codex script)
- Claude Code bootstrap documentation (.claude-plugin/bootstrap.md)
- Test suite runner and integration tests
- Markdown linting configuration

### Changed
- Enhanced install.sh with platform-specific setup functions
- README updated with platform compatibility table and autonomous mode notes
