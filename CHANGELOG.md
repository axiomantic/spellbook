# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.10] - 2026-02-19

### Changed
- **CLAUDE.spellbook.md slimmed ~38%** (601 -> 372 lines, ~3,500 token savings per session)
  - Removed duplicate Skill Execution section (was stated twice)
  - Condensed Code Quality, Intent Interpretation, Subagent Dispatch Enforcement, Compacting, No Assumptions elaboration, and YOLO Mode sections to stubs referencing existing skills/commands
  - Moved Context Minimization Protocol and Subagent Dispatch Template to `dispatching-parallel-agents` skill
  - Moved Branch-Relative Documentation to `finishing-a-development-branch` skill
  - Removed File Reading Protocol detail (already in `smart-reading` skill)
  - Compressed all 49 Skill Registry descriptions from 20-60 words to 8-15 words each
- **resolving-merge-conflicts skill v1.1.0** - Strengthened synthesis mandate with three improvements:
  - Added "Why Synthesis Matters" section with emotional stakes framing (picking ours/theirs = declaring the other developer's work worthless)
  - Added concrete before/after synthesis example showing rate limiting + sanitization conflict with WRONG (ours), WRONG (theirs), and CORRECT (synthesis) resolutions
  - Strengthened self-check with Mechanical Synthesis Test: describe each resolution in one sentence; if it contains "kept X's version" or "went with ours/theirs", you are selecting, not synthesizing
- **merging-worktrees skill** - Added Pre-Conflict Gate requiring `resolving-merge-conflicts` skill to be loaded in subagent context before any conflict resolution, preventing LLM base-model bias toward ours/theirs selection
- **dispatching-parallel-agents skill** - Added Context Minimization Protocol and Subagent Dispatch Template sections (moved from CLAUDE.spellbook.md)
- **finishing-a-development-branch skill** - Added Branch-Relative Documentation section (moved from CLAUDE.spellbook.md)
- **writing-skills skill** - Added "Writing Effective Skill Descriptions" section with description anatomy, trigger phrase guidance, model descriptions, anti-patterns table, and overlap disambiguation guidelines
- **24 skill descriptions improved** - Added natural-language trigger phrases, anti-triggers, and disambiguation to skills rated NEEDS_IMPROVEMENT in trigger adequacy audit: test-driven-development, debugging, fixing-tests, code-review, requesting-code-review, writing-plans, brainstorming, devils-advocate, reviewing-design-docs, gathering-requirements, dehallucination, instruction-engineering, using-git-worktrees, merging-worktrees, dispatching-parallel-agents, smart-reading, using-skills, using-lsp-tools, documenting-tools, tarot-mode, distilling-prs, advanced-code-review, auditing-green-mirage, async-await-patterns

### Added
- **Security hardening: defense-in-depth** - Comprehensive security layer for prompt injection, privilege escalation, and data exfiltration protection
  - Runtime input/output checking via `spellbook_mcp/security/` module (rules engine, scanner, tools)
  - 7 Claude Code hooks: `bash-gate.sh`, `spawn-guard.sh`, `state-sanitize.sh`, `audit-log.sh`, `canary-check.sh` + OpenCode `opencode-plugin.ts`
  - Gemini CLI security policy (`hooks/gemini-policy.toml`)
  - Trust registry with security modes (standard/elevated/paranoid)
  - Canary tokens for exfiltration detection
  - Honeypot tools to trap injection attempts
  - Workflow state validation with hostile pattern detection in `resume.py`
  - Supply chain scanner (`scripts/scan_supply_chain.py`)
  - Pre-commit security changeset scanning hook
  - **security-auditing skill** for security review workflows
  - Security sections added to CLAUDE.spellbook.md (output sanitization, injection awareness, least privilege, content trust boundaries, spawn protection, workflow state integrity, subagent trust tiers)
  - Multi-platform installer support for hooks (Claude Code, OpenCode, Gemini)
  - 20+ test files with ~1,000 security-specific tests

## [0.9.9] - 2026-02-12

### Added
- **Branch-Relative Documentation rule** - New inviolable rule in CLAUDE.spellbook.md requiring changelogs, PR descriptions, PR titles, and code comments to reflect only the merge-base diff, not session-by-session development history. Includes prohibition on historical code comments and a first-time reader test.

## [0.9.8] - 2026-02-09

### Added
- **Comprehensive health check** - Enhanced `spellbook_health_check` MCP tool with domain-specific checks
  - 6 domain checks: database, watcher, filesystem, github_cli, coordination, skills
  - Quick mode (liveness) vs full mode (readiness) with `full` parameter
  - HealthStatus enum: HEALTHY, DEGRADED, UNHEALTHY, UNAVAILABLE, NOT_CONFIGURED
  - Status aggregation with critical domain handling (database, filesystem are critical)
  - Detailed domain results with latency tracking and diagnostic details
  - New `spellbook_mcp/health.py` module (700+ lines)
  - 93 new tests for health check functionality
- **verifying-hunches skill** - Prevents premature eureka claims during debugging
  - Triggers on: "I found", "this is the issue", "root cause", "smoking gun", "aha", "got it"
  - Eureka registry tracks hypotheses with UNTESTED/TESTING/CONFIRMED/DISPROVEN status
  - Deja vu check prevents rediscovering same disproven theory after compaction
  - Specificity requirements: exact location, mechanism, symptom link, testable prediction
  - Test-before-claim protocol with prediction vs actual comparison
  - Confidence calibration language ("hypothesis" not "found")
- **isolated-testing skill** - Enforces methodical debugging with one-theory-one-test discipline
  - Triggers on chaos indicators: "let me try", "maybe if I", "what about", rapid context switching
  - Design-before-execute: write complete repro test before running anything
  - Approval gate (skipped in autonomous/YOLO mode)
  - FULL STOP on reproduction - announce and wait, no continued investigation
  - Theory tracker with explicit status management
  - Integrated into debugging, scientific-debugging, systematic-debugging
- **sharpening-prompts skill** - QA workflow for LLM instruction review
- **debugging Phase 0: Prerequisites** - Mandatory gates before any investigation
  - 0.1 Establish clean baseline: known-good reference state required before debugging
  - 0.2 Prove bug exists: hard gate requiring reproduction on clean baseline
  - 0.3 Code state tracking: always know what state you're testing
  - New invariant principles: baseline before investigation, prove bug exists first
  - Prevents: winging it without methodology, testing modified code, elaborate fixes before proving bug exists
- **"No Assumptions, No Jumping Ahead" inviolable rule** in CLAUDE.spellbook.md
  - Prevents LLM from guessing user intent or jumping straight to design/implementation
  - Requires exploring the space with user, asking questions, confirming approach before committing
  - Self-check gate: "Did the user confirm this, or did I decide for them?"
  - Reconciles with Intent Interpretation: invoke skill immediately, but linger in discovery phase
- **deep-research skill** - Multi-threaded web research with verification and hallucination prevention
  - Orchestrator skill + 3 commands: interview, plan, investigate
  - Phase 0 (interview): 5-category structured interview, assumption extraction, Research Brief output
  - Phase 1 (plan): thread decomposition, 4-phase source strategy (survey/extract/diversify/verify), round budgets
  - Phase 2 (investigate): novel triplet search engine [Scope/Search/Extract] with plateau detection and micro-reports
  - Phase 3 (verify): invokes existing fact-checking + dehallucination skills on findings
  - Phase 4 (synthesize): template selection by research type (comparison/procedural/exploratory/evaluative)
  - Subject Registry prevents entity dropout across parallel threads
  - Conflict Register enforces dual-position documentation when sources disagree
  - Override Protocol prevents silent changes to user-provided facts
  - Plateau Circuit Breaker with 3 escalation levels and drift detection
  - 6-level confidence tagging: VERIFIED, CORROBORATED, PLAUSIBLE, INFERRED, UNVERIFIED, CONTESTED
  - Composes existing skills: fact-checking, dehallucination, smart-reading, dispatching-parallel-agents patterns

### Changed
- **implementing-features Context Minimization** - Rewritten with explicit tool allowlist/blocklist
  - Allowlist: Task, AskUserQuestion, TaskCreate/Update/List, Read (plan docs only)
  - Blocklist: Write, Edit, Bash, Grep, Glob, Read (source files)
  - Narrates the exact failure pattern and correct pattern to internalize
  - Explains why orchestrator violations waste tokens and degrade quality
- **writing-commands skill+commands split** - Split oversized skill (2340 tokens) into orchestrator + 3 commands
  - Orchestrator SKILL.md: 128 lines (under 1500 token budget)
  - `writing-commands-create`: command schema, naming, frontmatter, token efficiency, example
  - `writing-commands-review`: quality checklist, anti-patterns, testing protocol
  - `writing-commands-paired`: paired command protocol, assessment framework integration
- **isolated-testing code state tracking** - Enhanced theory testing discipline
  - Step 0: Verify code state before selecting theory
  - Queue discipline: test theories in order, no skipping to "the likely one"
  - Code state violations added to FORBIDDEN section

### Fixed
- **Flaky token budget compliance tests** - Added 10% tolerance margin for LLM estimation variance
  - Skills between 1500-1650 estimated tokens produce warnings (not failures)
  - Skills over 1650 still fail (catches genuinely over-budget skills)
  - Eliminates random pass/fail on borderline skills across runs

## [0.9.7] - 2026-02-08

### Added
- **/design-assessment command** - Generate assessment frameworks for evaluative skills/commands
  - Detects target type (code, document, api, test, claim, artifact, readiness)
  - Generates dimension tables, severity levels, finding schemas, verdict logic
  - Supports autonomous and interactive modes
  - Integrates with brainstorming, writing-skills, and writing-commands skills

## [0.9.6] - 2026-02-03

### Fixed
- **MCP session init timeout** - Fixed `spellbook_session_init` hanging/aborting when `ctx.list_roots()` fails
  - Changed exception handler from `except Exception` to `except BaseException` to catch `asyncio.CancelledError` and `AbortError`
  - Added 1-second timeout to `list_roots()` call to prevent indefinite hangs
  - Gracefully falls back to `os.getcwd()` if client doesn't respond

## [0.9.5] - 2026-02-02

### Added
- **writing-commands skill** - Skill for creating and reviewing spellbook commands
  - Command schema with required sections: MISSION, Invariant Principles, Phases, FORBIDDEN
  - Paired command pattern for create/remove workflows (e.g., test-bar/test-bar-remove)
  - Quality checklist for command review mode
  - Reasoning tags (`<analysis>`, `<reflection>`) enforcement
- **test-bar command** - Generate floating QA test overlay for visual testing
  - Analyzes branch diff to identify conditional rendering paths
  - Creates one-click scenario buttons for each visual state
  - Dev-only guard with `__DEV__` or `NODE_ENV` checks
  - Manifest tracking for clean removal
- **test-bar-remove command** - Clean removal of test-bar overlay
  - Reads manifest created by test-bar
  - Surgically removes injected code
  - Verifies clean removal with git status check
- **Managing Artifacts skill** - New skill for artifact storage and project-encoded paths
  - Triggers on: "save report", "write plan", "where should I put", "project-encoded"
  - Covers artifact directory structure, project encoding, open source handling
- **Advanced Code Review skill** - New 5-phase code review workflow with verification
  - Phase 1: Strategic Planning - scope analysis, risk categorization, priority ordering
  - Phase 2: Context Analysis - load previous reviews, PR history, declined items
  - Phase 3: Deep Review - multi-pass code analysis, finding generation
  - Phase 4: Verification - fact-check findings, remove false positives
  - Phase 5: Report Generation - produce final deliverables
  - Tracks previous review decisions (declined, partial agreement, alternatives)
  - Claim extraction algorithm verifies findings against actual code
  - Outputs to `~/.local/spellbook/docs/<project>/reviews/`
- **Code Review Commands** - 5 phase-specific commands for advanced-code-review
  - `/advanced-code-review-plan` - Phase 1 strategic planning
  - `/advanced-code-review-context` - Phase 2 context analysis
  - `/advanced-code-review-review` - Phase 3 deep review
  - `/advanced-code-review-verify` - Phase 4 verification
  - `/advanced-code-review-report` - Phase 5 report generation
- **Session Resume** - Automatic continuation of prior work sessions
  - Detects recent sessions (<24h) and offers to resume
  - Generates boot prompts following handoff.md Section 0 format
  - Tracks active skill, phase, pending todos, workflow pattern
  - Continuation intent detection: explicit ("continue"), fresh start ("new session"), or neutral
  - Planning document detection from recent files
  - Pending todos counter with corruption detection
- **A/B Testing Framework** - Full experiment management for skill versions
  - `experiment_create` - Create experiments with control/treatment variants
  - `experiment_start`, `experiment_pause`, `experiment_complete` - Lifecycle management
  - `experiment_status`, `experiment_list` - Query experiments
  - `experiment_results` - Compare variant performance with metrics
  - Deterministic variant assignment based on session ID
  - Telemetry sync for outcome-to-experiment linking
  - Database schema: experiments, variants, assignments tables
- **Context Curator Plugin** (OpenCode) - Intelligent context management for long sessions
  - Automatic pruning strategies: `supersede-writes`, `purge-errors`
  - LLM-driven discard tool for selective context removal
  - MCP client with graceful degradation
  - Tool cache synchronization
  - Message pruning and context injection
  - Session state management with versioning
  - Curator analytics MCP tools for tracking prune events
- **OpenCode Claude Code behavioral standards** - Inject Claude Code's system prompts into OpenCode via `instructions` config
  - Synthesized prompt covers: read-before-modify, security awareness, anti-over-engineering, git safety, professional objectivity
  - Applies to ALL agents universally (beneath YOLO mode, always active)
  - Installed as symlink to `~/.config/opencode/instructions/claude-code-system-prompt.md`
- **OpenCode YOLO agents** - Two new agent definitions for autonomous execution
  - `yolo`: Full permissions, all tools enabled, auto-approve all operations
  - `yolo-focused`: Same permissions but with focused behavioral guidelines
- **Workflow state MCP tools** - New tools for managing feature workflow state
  - `workflow_state_get`, `workflow_state_set`, `workflow_state_clear`
  - Persistent storage in spellbook database
- **Phased slash commands** - Decomposed large skills into focused command sequences
  - `/feature-*`: discover, research, design, config, implement
  - `/dead-code-*`: setup, analyze, report, implement
  - `/simplify-*`: analyze, transform, verify
- **Mechanical phase-skip prevention** - implementing-features skill now enforces phase sequencing with bash artifact checks at sub-command entry points
  - Each sub-command (feature-research, feature-discover, feature-design, feature-implement) has a MANDATORY PREREQUISITE CHECK block that verifies prior phase artifacts exist before proceeding
  - Checks include tier verification, artifact existence (ls commands), and anti-rationalization reminders
- **Task Complexity Router** - New Phase 0.7 in feature-config classifies tasks into 4 tiers using mechanical heuristics
  - 5 heuristics: file count (grep-based), behavioral change, test impact, structural change, integration points
  - Tier derivation matrix maps heuristic results to Trivial/Simple/Standard/Complex
  - Executor proposes tier from heuristics, user confirms or overrides
  - Trivial exits the skill entirely; Simple follows a reduced-ceremony path; Standard/Complex run full workflow
- **Simple Path workflow** - Reduced-ceremony path for simple tasks (Config -> Lightweight Research -> Inline Plan -> Implement)
  - Quantitative guardrails enforce boundaries (max 5 research files, 5 plan steps, 5 impl files, 3 test files)
  - Exceeding any guardrail triggers mandatory upgrade to Standard tier
  - No external artifacts produced; research summary and plan are inline
- **Anti-Rationalization Framework** - Dedicated section in SKILL.md naming 7 common LLM shortcut patterns
  - Scope Minimization, Expertise Override, Time Pressure, Similarity Shortcut, Competence Assertion, Phase Collapse, Escape Hatch Abuse
  - Each pattern has signal phrases for detection and explicit counters
  - Brief anti-rationalization reminders at each prerequisite check point in sub-commands
- **Phase Transition Protocol** - Mechanical verification between phase transitions in SKILL.md
  - Anti-Skip Circuit Breaker with bash verification template
  - Complexity Upgrade Protocol for mid-execution tier changes when Simple path guardrails are exceeded
- **Tier-aware routing in feature-implement** - Prerequisite check branches on complexity tier
  - Simple tier navigates directly to Phase 4 (skipping Phase 3 planning)
  - Standard/Complex tiers require design document verification via ls
- **Multi-Phase Skill Architecture mandate** - writing-skills skill now requires orchestrator-subagent separation for multi-phase skills
  - 3+ phase skills MUST separate orchestrator from phase commands; 2 phases SHOULD; 1 phase exempt
  - Core rule: orchestrator dispatches subagents (Task tool), subagents invoke phase commands (Skill tool), orchestrator never invokes commands directly
  - Content split matrix defines what belongs in orchestrator (<300 lines: phase sequence, dispatch templates, shared data structures) vs phase commands (implementation logic, scoring, wizards)
  - Data structure placement criterion: referenced by 2+ phases = orchestrator, 1 phase = command
  - Exceptions for config/setup phases requiring user interaction and error recovery
  - 4 named anti-patterns for context bloat
  - Self-Check updated with multi-phase compliance checkbox
- **Skill analyzer tests** - 31 unit tests covering extraction, correction detection, version parsing, metrics aggregation

### Changed
- **Multi-Phase Skill Architecture compliance** - Refactored all 12 non-compliant skills to separate orchestrator SKILL.md from phase command files
  - Orchestrators slimmed to keep only: phase sequence, dispatch templates, shared data structures (referenced by 2+ phases), quality gates, anti-patterns
  - Phase-specific implementation logic, scoring formulas, checklists, and review protocols moved to dedicated command files
  - 30 new command files created in `commands/` directory, each with YAML frontmatter and self-contained for subagent independence
  - Shared data structures intentionally duplicated in relevant command files for subagent self-containment
- **CLAUDE.spellbook.md template optimization** - Reduced from 41KB to 22KB (~19KB savings)
  - Removed redundant skill registry (skills are natively discovered by coding assistants)
  - Extracted subagent decision heuristics to `dispatching-parallel-agents` skill
  - Extracted artifact management content to new `managing-artifacts` skill
  - Extracted task output storage to `dispatching-parallel-agents` skill
  - Trimmed glossary to essential terms only
- **Enhanced dispatching-parallel-agents skill** - Now includes subagent decision heuristics and task output storage
- **AGENTS.md size limit guidance** - Added documentation for splitting large skills into orchestrator + commands pattern
  - Skills exceeding 1900 lines / 49KB should be split, not trimmed
  - Skill becomes thin orchestrator, commands contain phase logic
- **Orchestrator pattern reinforcement** - Updated CLAUDE.spellbook.md and workflow skills
  - Clarified orchestrator role: dispatch subagents, don't do work in main context
  - Added OpenCode agent inheritance (YOLO type propagation to subagents)
- **Skill size reduction** - Major skills condensed to fit OpenCode's 50KB tool output limit
  - `implementing-features`: 90KB → under 50KB (phased command approach)
  - `finding-dead-code`: Reduced and split into phased commands
  - `simplify`: Reduced and split into phased commands
- **Handoff command enhanced** - More comprehensive context preservation for session continuation
- **SKILL.md Workflow Overview** - Expanded to include Phase 0.7, tier routing branches, and Simple Path appendix
- **SKILL.md Command Sequence table** - Added "Tier" column showing which complexity tiers use each command
- **SKILL.md SessionPreferences** - Added `complexity_tier` and `complexity_heuristics` fields
- **feature-config Phase 0 Complete checklist** - Added complexity tier classification and tier routing items
- **Intentional PR feedback framework** - Expanded `code-review --feedback` mode with structured response workflow
  - Gather feedback holistically across related PRs before responding
  - Categorize each item: Accept / Push back / Clarify / Defer
  - Document rationale for each decision
  - Response templates for each category
- **README Superpowers attribution** - Fact-checked and corrected attribution table
  - Removed inaccurate Origin columns from Skills/Commands/Agents tables
  - Added † markers to indicate Superpowers-derived items
  - Created dedicated Acknowledgments table with verified mappings

### Fixed
- **Session counts shared between projects** - MCP tools now use the client's working directory from MCP roots instead of the server's `os.getcwd()`. This fixes sessions appearing shared across all projects because the MCP server process has a different cwd than Claude Code.
  - Added `get_project_path_from_context()` and `get_project_dir_from_context()` async functions to extract project path from MCP roots
  - Converted `find_session`, `list_sessions`, `spawn_claude_session`, `spellbook_check_compaction`, `spellbook_context_ping`, `spellbook_session_init`, and `spellbook_analytics_summary` to async
  - Updated `inject_recovery_context` decorator to support async functions
  - Falls back to `os.getcwd()` when roots are unavailable for backward compatibility
- **OpenCode HTTP transport** - Use HTTP transport to connect to spellbook MCP daemon instead of stdio
- **Deprecated datetime.utcnow()** - Replaced with datetime.now(UTC) throughout codebase
- **MCP daemon PATH for CLI tools** - launchd/systemd services now set PATH correctly so tools like `gh` are accessible
  - macOS: Includes Homebrew paths for both Apple Silicon (`/opt/homebrew/bin`) and Intel (`/usr/local/bin`)
  - Linux: Includes Linuxbrew, `~/.local/bin`, `~/.cargo/bin`

### Skills Refactored (12 total)

| Skill | Before | After | Command Files |
|-------|--------|-------|---------------|
| fact-checking | 324 lines | 233 lines | fact-check-extract, fact-check-verify, fact-check-report |
| reviewing-impl-plans | 443 lines | 189 lines | review-plan-inventory, review-plan-contracts, review-plan-behavior, review-plan-completeness |
| auditing-green-mirage | 543 lines | 238 lines | audit-mirage-analyze, audit-mirage-cross, audit-mirage-report |
| reviewing-design-docs | 275 lines | 121 lines | review-design-checklist, review-design-verify, review-design-report |
| fixing-tests | 391 lines | 226 lines | fix-tests-parse, fix-tests-execute |
| requesting-code-review | 206 lines | 90 lines | request-review-plan, request-review-execute, request-review-artifacts |
| project-encyclopedia | 273 lines | 180 lines | encyclopedia-build, encyclopedia-validate |
| merging-worktrees | 263 lines | 179 lines | merge-worktree-execute, merge-worktree-resolve, merge-worktree-verify |
| finishing-a-development-branch | 255 lines | 179 lines | finish-branch-execute, finish-branch-cleanup |
| code-review | 285 lines | 157 lines | code-review-feedback, code-review-give, code-review-tarot |
| writing-skills | 365 lines | 312 lines | write-skill-test |
| reflexion | 171 lines | 124 lines | reflexion-analyze |

### New Command Files (32 total)
- `commands/test-bar.md` - Generate floating QA test overlay for visual testing
- `commands/test-bar-remove.md` - Clean removal of test-bar overlay
- `commands/fact-check-extract.md` - Phase 2-3: Extract and triage claims from code
- `commands/fact-check-verify.md` - Phase 4-5: Verify claims against source with evidence
- `commands/fact-check-report.md` - Phase 6-7: Generate findings report with bibliography
- `commands/review-plan-inventory.md` - Phase 1: Context, inventory, and work item classification
- `commands/review-plan-contracts.md` - Phase 2: Interface contract audit (type/schema/event/file)
- `commands/review-plan-behavior.md` - Phase 3: Behavior verification and fabrication detection
- `commands/review-plan-completeness.md` - Phase 4-5: Completeness checks and escalation
- `commands/audit-mirage-analyze.md` - Phase 1-2: Per-file anti-pattern analysis with scoring
- `commands/audit-mirage-cross.md` - Phase 3: Cross-cutting analysis across test suite
- `commands/audit-mirage-report.md` - Phase 4-5: Report generation and fix plan
- `commands/review-design-checklist.md` - Phase 1-2: Document inventory and completeness checklist
- `commands/review-design-verify.md` - Phase 3-4: Hand-waving detection and interface verification
- `commands/review-design-report.md` - Phase 5-7: Implementation simulation, findings, and remediation
- `commands/fix-tests-parse.md` - Phase 1: Parse and classify test failures
- `commands/fix-tests-execute.md` - Phase 2-4: Fix execution with TDD loop and verification
- `commands/request-review-plan.md` - Phase 1: Review planning and scope analysis
- `commands/request-review-execute.md` - Phase 2: Execute review with checklists
- `commands/request-review-artifacts.md` - Phase 3: Generate review artifacts and reports
- `commands/encyclopedia-build.md` - Phase 1-3: Research, build, and write encyclopedia
- `commands/encyclopedia-validate.md` - Phase 4: Validate encyclopedia accuracy
- `commands/merge-worktree-execute.md` - Phase 1: Execute worktree merge sequence
- `commands/merge-worktree-resolve.md` - Phase 2: Resolve merge conflicts
- `commands/merge-worktree-verify.md` - Phase 3: Verify merge and cleanup
- `commands/finish-branch-execute.md` - Phase 1-2: Analyze branch and execute chosen strategy
- `commands/finish-branch-cleanup.md` - Phase 3: Post-merge cleanup
- `commands/code-review-feedback.md` - Feedback mode: Process received code review feedback
- `commands/code-review-give.md` - Give mode: Review others' code
- `commands/code-review-tarot.md` - Tarot mode: Roundtable-style collaborative review
- `commands/write-skill-test.md` - Phase 5: Skill testing with pressure scenarios
- `commands/reflexion-analyze.md` - Full reflexion analysis workflow

## [0.9.4] - 2026-01-26

### Added
- **Skill usage analysis** - New `analyzing-skill-usage` skill and `analyze_skill_usage` MCP tool for measuring skill performance
  - A/B testing between skill versions (via `skill:v2` suffixes or `[v2]` in args)
  - Identifying weak skills by failure/correction rate
  - Metrics: completion rate, correction rate, token efficiency, failure score

## [0.9.3] - 2026-01-24

### Changed
- **Forge orchestration requires subagent execution** - autonomous-roundtable skill now mandates that forge orchestration runs in subagents, never main chat
- **Context overflow handoff protocol** - When orchestrator subagent approaches context limits, it generates a structured HANDOFF document and returns; main chat spawns successor orchestrator with full context transfer
- **Condensed autonomous-roundtable skill** - Reduced from 2249 to ~1000 tokens while preserving all critical functionality

## [0.9.2] - 2026-01-24

### Fixed
- **MCP server registered globally** - Claude Code MCP registration now uses `--scope user` instead of default local scope, making spellbook tools available in all projects without per-project registration

## [0.9.1] - 2026-01-24

### Fixed
- **MCP daemon import errors** - Fixed watcher thread import failures that caused 600K+ error log lines
  - Converted all imports to use full package paths (`from spellbook_mcp.x import...`)
  - Removed fragile sys.path manipulation from server.py
  - Added pyproject.toml for proper package installation
  - Updated daemon to run as module (`python -m spellbook_mcp.server`) instead of script
- **Watcher circuit breaker** - Watcher now gives up after 5 consecutive failures instead of infinite retry loop
- **Test isolation for pr_bless_pattern** - Fixed test pollution from global config directory

## [0.9.0] - 2026-01-22

### Added
- **Forged Autonomous Development System** - Meta-orchestration layer for brain-out project implementation
  - Database schema and models: `forge_tokens`, `iteration_state`, `reflections` tables
  - Artifact storage: path generation, CRUD operations for feature artifacts
  - Iteration MCP tools: `forge_iteration_start`, `forge_iteration_advance`, `forge_iteration_return`
  - Project graph: `FeatureNode`, `ProjectGraph`, dependency ordering with cycle detection
  - Project MCP tools: `forge_project_init`, `forge_project_status`, `forge_feature_update`, `forge_select_skill`
  - Validator infrastructure: `VALIDATOR_CATALOG` with 12 validators across 4 archetypes
  - Context filtering: `truncate_smart`, `select_relevant_knowledge`, `similarity`, token budget management
  - Roundtable MCP tools: `forge_roundtable_convene`, `forge_roundtable_debate`, `forge_process_roundtable_response`
  - Verdict parsing: regex-based extraction of archetype verdicts from LLM responses
  - OpenCode plugin: TypeScript extension for stage tracking and roundtable integration
  - 330 tests covering all forged modules

- **7 New Skills for Autonomous Development**
  - `autonomous-roundtable`: Meta-orchestrator for complete forge workflow
  - `gathering-requirements`: DISCOVER stage using archetype perspectives (Queen/Emperor/Hermit/Priestess)
  - `dehallucination`: Factual grounding with confidence assessment and recovery protocols
  - `reflexion`: Learning from ITERATE verdicts with pattern detection
  - `analyzing-domains`: DDD-based domain exploration with agent recommendation engine
  - `assembling-context`: Three-tier context organization with token budget management
  - `designing-workflows`: State machine design with transitions, guards, and error handling

- **Unified `code-review` skill** - consolidates all review functionality into one skill
  - `--self` mode: Pre-PR self-review (replaces `requesting-code-review`)
  - `--feedback` mode: Process received feedback (replaces `receiving-code-review`)
  - `--give <target>` mode: Review someone else's code (NEW)
  - `--audit [scope]` mode: Comprehensive multi-pass review (NEW)
  - `--tarot` modifier: Optional roundtable dialogue with personas
  - Target detection: PR numbers, GitHub URLs (with repo extraction), and branch names
  - Edge case handling: empty diffs, missing comments, oversized diffs with truncation
  - Finding deduplication: merges findings at same location, keeps highest severity

- **MCP infrastructure for code-review** - backend modules for the skill
  - `code_review/arg_parser.py` - argument parsing with mode detection
  - `code_review/models.py` - data models (Finding, PRData, FileDiff, etc.)
  - `code_review/router.py` - mode routing with target type detection
  - `code_review/edge_cases.py` - early detection of workflow-affecting conditions
  - `code_review/deduplication.py` - finding deduplication by file:line

### Changed
- **12 skills renamed to gerund pattern** for naming consistency
  - `domain-analysis` → `analyzing-domains`
  - `context-assembly` → `assembling-context`
  - `workflow-design` → `designing-workflows`
  - `code-quality-enforcement` → `enforcing-code-quality`
  - `design-doc-reviewer` → `reviewing-design-docs`
  - `implementation-plan-reviewer` → `reviewing-impl-plans`
  - `merge-conflict-resolution` → `resolving-merge-conflicts`
  - `green-mirage-audit` → `auditing-green-mirage`
  - `pr-distill` → `distilling-prs`
  - `instruction-optimizer` → `optimizing-instructions`
  - `worktree-merge` → `merging-worktrees`
  - `requirements-gathering` → `gathering-requirements`

### Enhanced
- **implementing-features skill** - Mandatory quality gates for swarmed execution
  - Work packet template with 5 required gates: implementation completion, code review, fact-checking, green mirage audit, test suite
  - README.md template with execution protocol and gate summary
  - Swarmed Execution anti-patterns in FORBIDDEN section
  - Phase 3.5 self-check items for work packet quality

### Deprecated
- `requesting-code-review` skill (use `code-review --self`)
- `receiving-code-review` skill (use `code-review --feedback`)

## [0.8.0] - 2026-01-21

### Added
- **PR-distill Python MCP migration** - moved from JavaScript CLI to Python MCP tools
  - `pr_fetch` - fetch PR metadata and diff from GitHub
  - `pr_diff` - parse unified diff into FileDiff objects
  - `pr_files` - extract file list from pr_fetch result
  - `pr_match_patterns` - match heuristic patterns against file diffs
  - `pr_bless_pattern` - bless a pattern for elevated precedence
  - `pr_list_patterns` - list all available patterns (builtin and blessed)
  - Foundation modules: errors, types, patterns, config, parse, matcher, bless, fetch
  - Removed JavaScript implementation after Python migration complete
  - Updated skill to use MCP tools instead of CLI

### Enhanced
- **Tarot mode documentation** - updated to list all 10 archetypes
- **Recovery testing** - added comprehensive before/after recovery e2e test

## [0.7.7] - 2026-01-21

### Fixed
- **Update check now runs for all existing repos** - fixed issue where update check only ran during clone, not when existing repo was found via `find_spellbook_dir()`
  - Now checks for updates in `bootstrap()` when existing repo is found
  - Re-execs updated installer after pull to use latest install.py
- **Symlink creation handles empty directories** - `create_symlink()` now removes empty directories blocking symlink creation (common after failed installs)
  - Empty directories are automatically removed and replaced with symlinks
  - Non-empty directories still fail with clear message to remove manually

## [0.7.6] - 2026-01-21

### Added
- **Smart update detection for existing installations** - installer now checks if repo is actually outdated before prompting
  - New `check_repo_needs_update()` function performs `git fetch` and compares commits behind remote
  - If already up-to-date: no prompt, just "Already at latest version"
  - If behind + headless/non-TTY: auto-updates without prompting
  - If behind + interactive: prompts with commit count (e.g., "5 commits behind main")
  - Gracefully handles network failures with warning and continues with existing version

## [0.7.5] - 2026-01-21

### Fixed
- **Installer patterns/docs symlink failure** - installer was creating `patterns` and `docs` as directories before attempting to symlink them, causing `[fail]` status on fresh installs

## [0.7.4] - 2026-01-19

### Enhanced
- **Code review skill interoperability** - handoff protocol between requesting and receiving skills
  - `requesting-code-review`: Added "Handoff to Receiving Skill" section with context preservation, invocation pattern, and provenance tracking (source: internal/external/merged)
  - `receiving-code-review`: Added "Handoff from Requesting Skill" section with context loading, finding reconciliation table, and shared context via review-manifest.json
  - Enables seamless transition from internal review to processing external PR feedback

## [0.7.3] - 2026-01-16

### Added
- **Zero-intervention session recovery** - Automatic context restoration after Claude Code compaction
  - Background watcher monitors session transcripts for compaction events
  - SQLite database stores 7 state components: todos, active skill, skill phase, persona, recent files, position, workflow pattern
  - MCP tool response injection via `<system-reminder>` tags using decorator pattern
  - No user action required; recovery context automatically injected into next MCP tool response
  - 96 new tests covering extractors, database, watcher, injection, and end-to-end recovery
- **Session continuation for implementing-features skill** - Resume interrupted workflows at exact position
  - `skill_phase` extractor detects highest phase reached in implementing-features sessions
  - Phase 0.5 Continuation Detection enables zero-intervention resume after compaction
  - Parses recovery context from `<system-reminder>`, verifies artifacts, re-collects preferences
  - Phase jump mechanism skips completed phases and resumes at correct position
  - 13 new tests for skill_phase extraction with comprehensive edge case coverage

### Fixed
- **Thread safety in recovery module** - Added locks for concurrent access
  - `threading.Lock` in `injection.py` for shared state (`_call_counter`, `_pending_compaction`)
  - `threading.Lock` in `db.py` for connection cache (`_connections`)
- **JSON error handling** - `build_recovery_context()` now gracefully handles corrupted JSON in database
- **Memory optimization** - Soul extractor uses `collections.deque(maxlen=200)` for efficient transcript reading
- **Markdown lint errors** - Fixed 12 pre-existing lint issues across project
  - Setext heading styles converted to ATX in `commands/address-pr-feedback.md`, `skills/project-encyclopedia/SKILL.md`
  - Table column counts fixed in `docs/commands/index.md`
  - Added `.markdownlint-cli2.jsonc` for proper ignore configuration

## [0.7.2] - 2026-01-16

### Fixed
- **MCP daemon session isolation** - Each Claude session now has isolated state
  - `mode` (fun/tarot/none) is now per-session instead of shared singleton
  - Added 3-day TTL with automatic cleanup of stale sessions
  - Backward compatible with stdio transport via `DEFAULT_SESSION_ID`
  - 12 new tests with green mirage audit verification
- **MCP daemon restart recovery** - Unknown session IDs now handled gracefully
  - Added `stateless_http=True` to prevent "Bad Request: No valid session ID provided" errors
  - Daemon restarts no longer break existing Claude sessions

### Changed
- **MCP transport config** - Updated `~/.claude.json` to use HTTP transport (`type: "http"`) instead of stdio for spellbook MCP server

## [0.7.1] - 2026-01-15

### Enhanced
- **`/crystallize` command** - comprehensive improvements based on restoration project learnings
  - Added **Phase 4.5: Iteration Loop** - self-iterates until output passes 8-check review
    - Circuit breaker: max 3 iterations to prevent infinite loops
    - 8 specific checks: closing anchor, CRITICAL count, explanatory tables, negative guidance, calibration notes, workflow cycles, enumerations, functional symbols
    - Forward progress rule: escalates if same issue appears twice
  - Added **Load-Bearing Content Identification** section - explicitly marks content types as UNTOUCHABLE
  - Added **Symbol Preservation Rules** - functional symbols (`✓ ✗ ⚠ ⏳`) distinguished from decorative emojis
  - Added **Table Preservation Rules** - protects explanatory columns ("Why X Wins", "Rationale", "Example")
  - Added **Calibration Content Rules** - preserves self-awareness notes ("You are bad at...")
  - Added **Section Preservation Rules** - keeps negative guidance as separate sections
  - Added **Emotional Architecture Rules** - templates for adding ROLE/FINAL_EMPHASIS when missing
  - Added **Pre-Crystallization Verification** - HALT gate before output with 9-item checklist
  - Added **Post-Synthesis Verification** - token count thresholds (<80% = HALT, >120% = warning)
  - Expanded **Anti-Patterns** - 7 new forbidden behaviors from empirical findings
  - Reorganized **Self-Check** - grouped by phase completion, content preservation, new rules

### Fixed
- **Crystallize over-compression restored** - 29 skills/commands recovered from aggressive crystallization
  - ~12,000 lines of load-bearing content restored via synthesis of OLD + CURRENT versions
  - Each file went through individual synthesis → review → iterate loop
  - Files with issues required fix iterations (6 files needed emotional architecture fixes)

## [0.7.0] - 2026-01-13

### Added
- **Tarot mode** - collaborative roundtable with 10 tarot archetypes for software engineering
  - `tarot-mode` skill: Four core personas (Magician, Priestess, Hermit, Fool) plus six specialized agents
  - Embeds EmotionPrompt (+8% accuracy) and NegativePrompt (+12.89% induction) in persona dialogue
  - Stakes-driven quality: "Do NOT skip X", "Users depend on Y" in all exchanges
  - Visible collaboration: personas talk TO each other, challenge, synthesize
  - Personas affect dialogue only, never code/commits/documentation
- **`/mode` command** - unified session mode switching
  - `/mode` shows current mode status with source (session vs config)
  - `/mode fun` switches to fun mode with random persona
  - `/mode tarot` switches to tarot roundtable mode
  - `/mode off` disables any active mode
  - Asks about permanence: save to config or session-only
- **6 tarot archetype agents** for roundtable dispatch
  - `chariot-implementer` - Implementation specialist, "Do NOT add features"
  - `emperor-governor` - Resource governor, "Do NOT editorialize"
  - `hierophant-distiller` - Wisdom distiller, "Find THE pattern"
  - `justice-resolver` - Conflict synthesizer, "Do NOT dismiss either"
  - `lovers-integrator` - Integration specialist, "Do NOT assume alignment"
  - `queen-affective` - Emotional state monitor, "Do NOT dismiss signals"
- **Session mode API** - new MCP tools for mode management
  - `spellbook_session_mode_set(mode, permanent)` - set mode with permanence option
  - `spellbook_session_mode_get()` - get current mode, source, and permanence
  - Session-only mode (in-memory, resets on MCP server restart)
  - Backward compatible with legacy `fun_mode` config key
- **Installer symlinks component** - modular symlink management in `installer/components/symlinks.py`

### Changed
- **`/toggle-fun` replaced by `/mode`** - unified command handles fun, tarot, and off states
  - `/toggle-fun` file removed
  - Use `/mode fun` for same functionality with permanence option
- **Session mode resolution** - priority order: session state > `session_mode` config > `fun_mode` legacy > unset
- **CLAUDE.spellbook.md** - added tarot mode documentation to Session Mode table

### Enhanced
- **`instruction-engineering` skill** - added content for tarot mode prompt construction

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

[Unreleased]: https://github.com/axiomantic/spellbook/compare/v0.9.1...HEAD
[0.9.1]: https://github.com/axiomantic/spellbook/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/axiomantic/spellbook/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/axiomantic/spellbook/compare/v0.7.7...v0.8.0
[0.7.7]: https://github.com/axiomantic/spellbook/compare/v0.7.6...v0.7.7
[0.7.6]: https://github.com/axiomantic/spellbook/compare/v0.7.5...v0.7.6
[0.7.5]: https://github.com/axiomantic/spellbook/compare/v0.7.4...v0.7.5
[0.7.4]: https://github.com/axiomantic/spellbook/compare/v0.7.3...v0.7.4
[0.7.3]: https://github.com/axiomantic/spellbook/compare/v0.7.2...v0.7.3
[0.7.2]: https://github.com/axiomantic/spellbook/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/axiomantic/spellbook/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/axiomantic/spellbook/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/axiomantic/spellbook/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/axiomantic/spellbook/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/axiomantic/spellbook/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/axiomantic/spellbook/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/axiomantic/spellbook/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/axiomantic/spellbook/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/axiomantic/spellbook/releases/tag/v0.1.0
