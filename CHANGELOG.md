# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.56.0] - 2026-04-29

### Added

- **PR Review Bot details.** Adds bot username and re-review command instructions to `AGENTS.md`.
- **ForgeCode harness support (basic tier).** ForgeCode
  (tailcallhq/forgecode) joins Claude Code, OpenCode, Codex, and
  Gemini CLI as a 5th supported harness. Includes a dedicated
  `ForgeCodeInstaller` that writes Claude-Code-style top-level
  `mcpServers` to `<config_dir>/.mcp.json` (created with `0o600`
  atomically), an AGENTS.md demarcated section, MCP health-check
  integration, daemon CLI-tools list registration, and post-install
  TUI/CLI messaging. The installer honors `$FORGE_CONFIG`, prefers a
  legacy `~/forge` directory when pre-existing, and falls back to
  `~/.forge` by default. Self-identification signal is the system
  prompt opening with `You are Forge`, `You are Sage`, or
  `You are Muse`.

### Changed

- **README and docs positioning.** Reframes user-facing documentation to
  articulate Spellbook as a harness-augmentation layer that runs across
  coding harnesses (Claude Code, OpenCode, Codex, Gemini CLI, ForgeCode),
  rather than a peer product. Surfaces three differentiators on the front
  page: harness-agnostic, shared centralized MCP server for cross-harness
  state continuity, and a skills+hooks layer no individual harness ships
  natively. Touches `README.md`, `docs/index.md`,
  `docs/getting-started/{platforms,quickstart}.md`, `AGENTS.spellbook.md`,
  and `pyproject.toml`.
- **`.gemini/styleguide.md` updated for the python-tripwire 0.20+
  rebrand.** bigfoot 0.21 is a thin namespace shim re-exporting
  python-tripwire; the `_mock` suffix on proxies was dropped and
  `[tool.tripwire]` is the canonical pyproject section. The styleguide
  now matches reality so contributor PRs are not flagged for
  conformance with stale aliases.
- **`pyproject.toml` dev deps** require `python-tripwire[http]`
  explicitly. The bigfoot 0.21 shim does not pull tripwire's `[http]`
  extra transitively, which surfaced as `ImportError: python-tripwire
  [http] is required` in CI.
- **Test suite migrated** from `bigfoot.{log,subprocess,db}_mock` to
  the renamed `bigfoot.{log,subprocess,db}` proxies (49 substitutions
  across 13 files) to track tripwire 0.20+.

## [0.55.0] - 2026-04-27

### Added

- **`/crystallize-consolidate` command** — operator-invoked rule
  bookkeeping for crystallize. Merges overlapping rules (with a
  `merged-from` provenance field), deprecates stale rules, and
  requires two-pass confirmation for removals. Operates only on the
  canonical `## Rules` section; never compresses General Instructions.
- **Crystallize Rules-section fixtures** under `tests/crystallize-fixtures/`:
  five fixture sets (mixed-format, no-rules, re-crystallize, byte-drift,
  mixed-tag-block) covering input detection, output emission, and
  byte-fidelity verification edge cases. Static input/expected pairs;
  no programmatic runner yet (disclosed in the fixture README).

### Changed

- **`crystallize` Rules / General split.** Crystallize now distinguishes
  lossless **Rules** (byte-preserved across passes, with provenance
  metadata) from synthesizable **General Instructions** (subject to
  normal compression). Detection is semantic with bias toward
  over-preservation. First-pass borderline content can be tightened
  with operator consent; in autonomous mode, tightening is silently
  skipped and surfaced in a `Tightening Skipped` delivery footer.
  Token-target arithmetic recomputes against
  `(total_bytes - rule_bytes)` with separate first-pass and
  re-crystallization envelopes plus a HALT floor enforced once in
  Post-Synthesis Verification.
- **`crystallize-verify` independent rule extractor.** The verifier no
  longer trusts the crystallizer's classification: any rule-shaped
  content present in the original but absent from the output Rules
  section is `CRITICAL`, regardless of how the crystallizer treated it.
  The verifier also accounts for consolidation via the `merged-from`
  field. Verifier read discipline preserved (only the two artifacts
  under review).
- **`optimizing-instructions` skill guard.** Inputs containing a
  `## Rules` heading are rejected with a redirect to `/crystallize`.
  The Rules-preservation carve-out is scoped to `crystallize` and
  `crystallize-consolidate`; `sharpen-improve` and other compression
  paths keep their own contracts.
- **`AGENTS.spellbook.md` Core Philosophy.** Adds *Steady correctness
  over speed — thoroughness is the default; speed is the exception
  that requires explicit operator instruction.* The existing
  **Develop = Thoroughness Mode** contract is positioned as a
  specialization of this umbrella.
- **`develop` skill phase non-fungibility hardened.** Adds a
  Pre-Dispatch Ritual that requires an explicit phase declaration
  before any subagent dispatch, bans the "subagents are HOW phases
  execute, not a substitute FOR phases" conflation in named-phrasing
  form, and codifies the thoroughness contract for Phase 4 gate
  sequencing (no batched gates across tasks).

## [0.54.1] - 2026-04-26

### Changed

- **Subagent skill dispatch contract hardened.** The canonical dispatch
  template in `dispatching-parallel-agents` now prohibits silent fallback:
  if the Skill tool is unavailable or the named skill is not in the
  catalog, the subagent must report the missing capability verbatim
  instead of inline-executing the skill from memory. The `develop`
  skill's "Subagent Skill Invocation Verification" block (mirrored in
  `commands/feature-implement.md` and `docs/skills/develop.md`) is now
  a hard REJECT rather than a prose-level "verify and re-dispatch",
  with explicit escalation when re-dispatch also fails.
- **Skill Availability by Agent Type matrix** added to
  `dispatching-parallel-agents`, documenting which subagent types
  (`general-purpose`, `Explore`, `Plan`, `yolo`, `yolo-focused`) include
  the Skill tool and which (`claude-code-guide`, `statusline-setup`)
  do not. Includes the lazy-injection caveat: the skills catalog
  system-reminder is platform-injected after a subagent's first tool
  call, not at session start.
- **`AGENTS.spellbook.md` Skill Execution rules** now explicitly name
  the "subagents are HOW each phase executes, not a substitute FOR the
  phases" conflation as a forbidden anti-pattern.
- **`AGENTS.md` Adding Config Options section** added: three-point rule
  for new user-facing config keys (prompt new users, prompt existing
  users only if unset, never re-prompt once answered), divergent
  install entry-point parity requirement, idempotency pattern,
  non-tty fallback discipline, and `--reconfigure` flag guidance.
- **Bigfoot mocking rule hardened in `AGENTS.md`** with explicit
  forbidden/allowed lists. Narrows the `monkeypatch` allowlist to env
  vars, cwd, and `sys.path` only. Adds reviewer-phrasing guidance to
  prevent "use bigfoot OR monkeypatch" suggestions.

## [0.54.0] - 2026-04-22

### Added

- **Worker LLM** (opt-in, fully feature-flagged, all flags default OFF):
  first direct LLM integration in spellbook, targeting cheap
  OpenAI-compatible local endpoints (Ollama, vllm-mlx, LM Studio, etc.)
  for passive/augmentation tasks. Capabilities each gate independently:
  transcript-harvesting memory on the Stop hook (replace/merge/skip
  modes); PreToolUse safety sniff with fail-open on worker outage and
  a persistent on-disk block cache; memory rerank composition inside
  `memory_recall`; optional Claude-memory read-side merge via a new
  `claude_memory` scanner and schema translator.
- **`forge_roundtable_convene_local` MCP tool** (async) for
  worker-LLM-powered roundtable execution without orchestrator tokens.
- **`spellbook worker-llm doctor` CLI** probes config, transport,
  prompts, safety cache, event publish path, and feature flags.
- **Shared installer wizards** under `installer/wizards/`: `worker_llm`
  for the new subsystem, `defaults` covering 7 previously-unprompted
  config keys (`notify_*`, `auto_update`, `session_mode`,
  `profile.default`). Both install entry paths (root `install.py` and
  `spellbook/cli/commands/install.py`) now share the same wizards;
  previously they had drifted. `--reconfigure` bypasses the
  `config_is_explicitly_set` idempotency gate.
- **`profile.default` CONFIG_SCHEMA entry** (was invisible to the admin
  UI before).
- **Hybrid event transport**: in-daemon publishes use in-process
  `EventBus.publish`; subprocess callers POST to root
  `/api/events/publish` with bearer auth. Resolves events dropped when
  emitted from hook subprocesses.
- **Worker-prompt overrides**: four default prompts ship in the wheel
  and are overrideable via `~/.local/spellbook/worker_prompts/<task>.md`
  with a breadcrumb README.
- **`tests/conftest.py` autouse fixture** that isolates
  `worker_llm_*` config reads from the developer's real environment,
  preventing the "passes locally, fails for others" class of bug.
- **`fractal_claim_work(..., session_id=)`** parameter, documented in
  the skill, command, and mirrored docs. Enables linking a claimed node
  to the worker's chat log for replay in the admin UI.
- **AGENTS.md "Adding Config Options" section** with the three-point
  rule: prompt new users, prompt existing users on reinstall if still
  unset, never re-prompt once answered.
- **Pre-commit hook (`check-admin-frontend`)** staged for a future
  admin-frontend lint+typecheck path; currently inert.

### Changed

- **Bigfoot-only mocking rule hardened** in AGENTS.md and
  `.gemini/styleguide.md`. Rewrites the mocking section to document
  the register -> sandbox -> assert paradigm and the three guarantees.
  Narrows the `monkeypatch` allowlist to env vars, cwd, and sys.path
  only. Replaces fabricated plugin names (`bigfoot.database`,
  `bigfoot.socket`, `bigfoot.patch`, `@bigfoot.mock` decorator) with
  the real API surface from bigfoot 0.19.2. Documents
  `bigfoot.db_mock` as a state-machine plugin with step sentinels and
  `assert_*` methods. Adds explicit forbidden/allowed reviewer phrasings
  so automated reviewers cannot suggest `monkeypatch` or fabricated
  APIs without the guidance catching it.
- **All worker_llm test files migrated to bigfoot**
  (`test_config.py`, `test_events.py`, `test_events_publish_route.py`,
  `test_transcript_harvest.py`). `unittest.mock` usage eliminated from
  the worker_llm test suite. Non-callable `monkeypatch.setattr` uses
  on module state (bool flags, Path constants, int counters) retained
  — they fall outside the bigfoot mocking paradigm. One narrow
  `monkeypatch` carve-out in `test_transcript_harvest.py` documents a
  bigfoot `SocketPlugin` / `asyncio.run()` interaction limitation at
  bigfoot 0.19.2.

### Removed

- **TTS subsystem** (breaking change): `spellbook/tts/` (~6000 lines),
  `tts_speak`/`tts_status`/`tts_session_set`/`tts_config_set` MCP
  tools, the TTS installer wizard, the `--no-tts` install flag,
  daemon-venv provisioning for sounddevice/wyoming, the
  `tts_enabled`/`tts_voice`/`tts_volume` config keys, the `[tts]`
  optional dependency, PortAudio CI install, sounddevice/wyoming deps,
  11 TTS-only test files. The `audio-notifications` skill now covers
  only OS notifications.
- **MCP tool surface pruned from 96 to 65 tools** (breaking change,
  −27 tools):
  - Deleted unused domains: `messaging` (8 tools, 0 callers),
    `experiments` (7 tools, 0 callers). Domain modules in
    `spellbook/messaging/` and `spellbook/experiments/` also removed.
  - Deleted dead tools: `spellbook_check_compaction`,
    `spellbook_context_ping`, `analyze_skill_usage`,
    `spellbook_analytics_summary`, `spellbook_inject_test_reminder`.
  - Removed telemetry MCP triad: `spellbook_telemetry_enable`,
    `spellbook_telemetry_disable`, `spellbook_telemetry_status`.
  - Deleted `forge_roundtable_debate` and `forge_select_skill`
    (0 callers).
  - Deleted `forge_feature_update` and
    `forge_process_roundtable_response` (0 callers — neither
    referenced from any skill, command, doc, or OpenCode extension).
    Underlying library functions retained in `spellbook/forged/`
    because they still have internal callers.
- **`render_config_wizard` stub** and a `WIZARD_CONFIG_KEYS` key-name
  drift in the installer.
- **TTS-related dependabot groups** (kokoro, soundfile, sounddevice);
  `daemon-core` simplified to a catch-all.

### Fixed

- **`ContextVar _MEMORY_RECALL_ERROR`** surfaces worker failures to
  `memory_recall` callers without raising, preserving the contract
  that `memory_recall` never fails hard.
- **Hook subprocess event publish path**: subprocess-originated events
  (e.g., from hook scripts) previously dropped silently; now routed
  through `/api/events/publish` with bearer auth.
- **CI `python-tests` job**: removed the now-invalid
  `uv sync --group tts` and the PortAudio system-install step left
  behind after the TTS removal.
- **Windows CI failure in `test_memory_integration.py`**: the rerank
  mock response was built via f-string interpolation of a
  `pathlib.Path`, so Windows temp paths (`C:\Users\runneradmin\...`)
  embedded raw backslashes that were rejected as invalid JSON escape
  sequences. Switched the three affected construction sites to
  `json.dumps(...)` so paths round-trip cleanly on every platform.

### Breaking Changes

- **TTS removed.** Any user or extension that called `tts_speak`,
  `tts_status`, `tts_session_set`, or `tts_config_set` must adapt. The
  `[tts]` extra, `--no-tts` install flag, and
  `tts_enabled`/`tts_voice`/`tts_volume` config keys no longer exist.
- **27 MCP tools removed.** Callers of the messaging domain,
  experiments domain, telemetry triad, `forge_roundtable_debate`,
  `forge_select_skill`, `forge_feature_update`,
  `forge_process_roundtable_response`, and the dead utility tools
  listed under "Removed" must migrate or drop those calls.

### Track 6: Worker LLM Observability

- **`worker_llm_calls` SQLite-backed rolling log** records every worker
  LLM call for operator introspection. Writes happen fire-and-forget
  from two paths: `publish_call` on the in-daemon publish path and the
  `/api/events/publish` route handler on the subprocess path. Writes
  are sync SQLAlchemy, wrapped in best-effort try/except with
  first-failure-loud logging so a DB hiccup never interrupts a
  worker call but also never fails silently forever.
- **First Alembic migration for the spellbook DB**
  (`0001_add_worker_llm_calls`). `alembic.ini` was wired up with
  `version_locations` for per-DB subdirectories so
  `alembic upgrade -x db=spellbook` now actually applies migrations to
  the live DB. Prior to this change the spellbook DB had no migration
  history path even though the Alembic scaffolding existed.
- **`tool_safety` fail-open path unified.** The prompt-load
  short-circuit that previously emitted via `publish_fail_open` now
  goes through `publish_call(status='fail_open')`, which routes to a
  new `call_fail_open` event_type inside `publish_call`'s routing
  logic. This makes fail-open events visible to the new admin
  dashboard alongside successes and errors. The `publish_fail_open`
  helper itself is left in place for a post-audit cleanup pass.
- **Admin API**: `GET /api/worker-llm/calls` (paginated, filterable
  list) and `GET /api/worker-llm/metrics` (success rate, p95, p99,
  error breakdown, total).
- **Admin page `/admin/worker-llm`** with `WorkerLLMPage`,
  `MetricCard`, `ErrorBreakdownCard`, React Query hooks
  `useWorkerLLMCalls` + `useWorkerLLMMetrics`, and a Sidebar nav link
  "// WORKER LLM CALLS".
- **Background tasks registered in the daemon lifespan**:
  `purge_loop` (batched `DELETE ... LIMIT 500`, fresh session per
  batch, enforces `retention_hours` + `max_rows` caps) and
  `threshold_eval_loop` (edge-triggered desktop notifications via the
  existing `notifications.notify.send_notification` when the success
  rate drops below threshold over the last N calls; recovery
  notification fires on return to healthy).
- **Seven new `CONFIG_SCHEMA` / `CONFIG_DEFAULTS` keys**:
  `worker_llm_observability_retention_hours` (24),
  `worker_llm_observability_max_rows` (10000),
  `worker_llm_observability_purge_interval_seconds` (300),
  `worker_llm_observability_notify_enabled` (false),
  `worker_llm_observability_notify_threshold` (0.8),
  `worker_llm_observability_notify_window` (20),
  `worker_llm_observability_notify_eval_interval_seconds` (60).
- **`spellbook worker-llm doctor` extended** with an observability
  health check: reports `worker_llm_calls` table presence and row
  count, last-row timestamp, last-purge timestamp, and notification
  subsystem reachability.

### Track 7: Async Queue, Warm Probe, Hook Observability, Config Audit

- **Async worker queue** (opt-in): bounded `asyncio.Queue` with a daemon
  consumer task and drop-oldest overflow semantics. New
  `POST /api/worker-llm/enqueue` endpoint colocated with
  `/api/events/publish` at the MCP root. Fire-and-forget worker-LLM paths
  (transcript_harvest and the new tool_safety warm probe) enqueue when
  `worker_llm_queue_enabled=True` and fall back to the sync call
  otherwise. Each overflow drop publishes a `call` event with
  `status="dropped"` so queue pressure is observable in the admin UI.
  Two config keys: `worker_llm_queue_enabled` (default False) and
  `worker_llm_queue_max_depth` (default 256).
- **Warm probe for tool_safety** (PreToolUse): when the last successful
  worker-LLM call is older than `worker_llm_tool_safety_cold_threshold_s`
  (default 45s), the PreToolUse path skips the sniff (fail-open) and
  kicks off a background warmup enqueue. Prevents cold-start latency
  from stalling tool invocations while keeping the worker primed.
- **Hook execution observability**: new `hook_events` SQLite table (one
  row per dispatcher invocation) plus `/api/hooks/record`,
  `/api/hooks/events`, and `/api/hooks/metrics` endpoints. New
  `/admin/hooks` page renders metric cards (p50/p95 duration, success
  rate, recent event count) and a filterable event table. Retention
  governed by three config keys (`hook_observability_retention_hours`,
  `hook_observability_max_rows`,
  `hook_observability_purge_interval_seconds`) matching the worker-LLM
  observability shape.
- **Admin config page now exposes 23 previously-hidden keys** (`fun_mode`,
  `persona`, `security.spotlighting.*`, `security.crypto.*`,
  `security.sleuth.*`, `security.lodo.*`). Schema entries grouped by
  dotted prefix so the admin UI can render collapsible sections. New
  `secret: True` schema flag masks values in `GET /api/config`
  responses; applied to `security.sleuth.api_key` and now also
  `worker_llm_api_key`. PUT handlers treat an incoming `"***"` on a
  secret key as a no-op for that key so a whole-config echo from the
  frontend cannot overwrite the real stored secret with the mask.
- **Runtime state file** `~/.local/spellbook/state.json` separated from
  `spellbook.json` to keep user-chosen config distinct from
  daemon-authored runtime state. Currently carries
  `update_check_failures` and `auto_update_branch`. A one-shot migration
  at `session_init` moves any legacy values out of `spellbook.json`.
- **`spellbook.json` dead keys removed**: `tts_enabled`, `tts_volume`,
  `telemetry_enabled`. The TTS subsystem was removed earlier in 0.54.0
  but these keys lingered in the schema; the migration also drops them
  from existing config files on first session_init.
- **Worker-LLM call `status` vocabulary normalized** to
  `{success, error, timeout, fail_open, dropped}` at the client publish
  site. Previously the client emitted raw `"ok"` and exception-class
  names (`"TimeoutError"`, `"ConnectionError"`, ...), which broke the
  admin-UI aggregate metrics, the threshold notifier, and the warm-probe
  "last success" calculation.
- **Background offload for observability writes**: shared
  `_spawn_background` helper in `spellbook/worker_llm/events.py` that
  runs a callable via `loop.run_in_executor` when an event loop is
  active and falls back to a direct sync call otherwise. Applied to
  `record_call` inside `publish_call` (daemon path) and to
  `record_hook_event` inside the `/api/hooks/record` route so the
  daemon event loop is never blocked on SQLite writer-lock contention.
- **Count-cap purge rewrite** in both
  `spellbook/worker_llm/observability.py` and
  `spellbook/hooks/observability.py`: replaces
  `DELETE ... WHERE id NOT IN (SELECT id ... LIMIT max_rows)` with an
  inlined scalar subquery `id <= (SELECT id ORDER BY id DESC OFFSET
  max_rows LIMIT 1)`. SQLite's support for LIMIT inside IN/NOT IN
  subqueries is compile-time optional, and the old pattern was O(N*M)
  because the keep-set was re-evaluated per batch. The new shape uses
  `IN` (always supported) against an indexed PK scan and terminates
  naturally when the OFFSET returns NULL.
- **`session_mode` config validation**: `_validate_config_value` now
  rejects values outside `{fun, tarot, none}` so an admin UI typo cannot
  land an invalid persisted mode. Mirrors the existing
  `worker_llm_transcript_harvest_mode` guard.
- **`ConfigField` value resync**: `spellbook/admin/frontend/src/pages/ConfigEditor.tsx`
  now resyncs the local `editValue` state via `useEffect` when the
  `value` prop changes externally (e.g., after a successful save
  refetches config, or when the user cancels an edit). Previously the
  field remained frozen on its first-mount value until the component
  unmounted.

## [0.53.1] - 2026-04-18

### Fixed

- **Installer dependency resolution**: `uv run install.py` ran the script
  under an isolated PEP 723 env with `dependencies = []`, so `rich`,
  `sqlalchemy`, and other project deps declared in `pyproject.toml` were
  never available at install time. Re-exec commands now use
  `uv run --project <repo> python <script>` to pick up the full project
  environment. Also added a final re-exec step for the curl-pipe path with
  an existing local repo, which previously fell through to `run_installation`
  under plain `python3` and crashed importing `rich`.
- **Daemon `/health` route silently missing**: `spellbook/mcp/routes.py`
  imported `spellbook.notifications.tts` at module scope, which pulled in
  `numpy` (part of the optional `tts` dep group). When TTS wasn't installed,
  the import failed and `register_all_tools()` swallowed the error, so
  `@mcp.custom_route("/health")` was never registered. The installer's
  health check then 404'd and reported daemon startup failure. Moved the
  `tts` import into the `/api/speak` handler so it's only loaded when that
  endpoint is actually called.

## [0.53.0] - 2026-04-15

### Added

- **File-based memory system** (replaces the SQLAlchemy-backed memory):
  frontmatter + body storage, QMD + Serena search backends, confidence and
  `last_verified` fields, access log, citation tracking, sync pipeline,
  secret scanner, migration tooling.
- **Confidence decay** applied lazily in scoring: `high → medium → low`
  multiplier (1.0 / 0.7 / 0.4) based on `last_verified` (or `created`
  fallback). `store_memory()` defaults `confidence="high"`. Sync pipeline
  `STILL_TRUE` verdict refreshes `last_verified`.
- **Automatic memory recall on hooks**: `UserPromptSubmit` and `PreToolUse`
  handlers extract keywords / paths, call `/api/memory/recall`, inject
  `<spellbook-memory-context>` into prompts. Budget 500 tokens / 5 memories.
  Atomic dedup log with 15-minute TTL. Config toggle `memory.auto_recall`
  (default true).
- **Automatic memory storage on hooks**: `UserPromptSubmit` pattern detection
  for corrections / confirmations / explicit remember; `Stop` hook harvests
  `<memory-candidate>` self-nominations from the assistant transcript.
  Rule-dictation exception. Partial-failure retry semantics. Config toggle
  `memory.auto_store` (default true). `AGENTS.spellbook.md` documents the
  self-nomination schema.
- **Admin API**: three filestore-backed endpoints — `GET /api/memories`,
  `/search`, `/{path:path}`. Path-traversal guard.

### Changed

- `/api/memory/recall` rewired to `filestore.recall_memories` with
  `cwd`-derived namespace.
- Admin frontend (`types.ts`, `useMemories.ts`, `MemoryBrowser.tsx`) updated
  to new schema (path-as-id, new Citation shape, `confidence`, `last_verified`).

### Removed

- ORM-backed memory endpoints: `/stats`, `/consolidate`, `/namespaces`,
  memory update/delete. No backwards compatibility (pre-1.0).

## [0.52.0] - 2026-04-14

### Added

- **Stable source symlink** (`~/.local/spellbook/source`) is now the canonical
  `$SPELLBOOK_DIR` for all installed artifacts. `install.py` creates or
  repoints this symlink on every run; hook commands, launchd plists,
  systemd units, and CLAUDE.md variable blocks reference the symlink
  rather than the resolved checkout path. Switching worktrees is now a
  one-command operation: re-run `install.py` from the new worktree and
  every artifact follows the symlink automatically.
- **Backup-then-symlink** when the target path exists as a real directory.
  With `--yes`, the existing directory is renamed to
  `source.backup-YYYYMMDD-HHMMSS` and replaced with the symlink. Without
  `--yes`, the installer aborts with an actionable error.
- **`spellbook_managed: true` + `spellbook_hook_id`** fields on every
  installer-written hook entry in `~/.claude/settings.json`. Re-installs
  dedup by these fields instead of matching paths, so re-installing from
  a different worktree replaces the old entries cleanly instead of
  appending duplicates.

### Changed

- **Daemon-venv editable install** is now refreshed when the source path
  changes (new `.source-path` marker), not just when `pyproject.toml`
  changes. Refresh runs `pip uninstall spellbook -y` twice (defensive,
  handles stale non-editable installs) before `pip install --no-deps -e`
  against the symlink path.

### Fixed

- Re-running `install.py` from a different worktree no longer leaves the
  `~/.claude/settings.json` hook array with duplicate
  `spellbook_hook.py` entries (one per worktree).
- Launchd plist `WorkingDirectory` and `SPELLBOOK_DIR` env now reference
  the stable symlink, so the daemon survives worktree moves without
  breaking.

## [0.51.0] - 2026-04-09

### Added
- **cco sandbox launcher**: `scripts/spellbook-sandbox` wraps [nikvdp/cco](https://github.com/nikvdp/cco) so Claude Code / OpenCode / Codex can run under YOLO mode with automatic sandboxing. The source tree is mounted read-only; the config directory is mounted read-only since hook subprocesses route writes (error logs, messaging state) through the daemon's HTTP API.
- **Sandboxing documentation**: New `## Sandboxing with cco (macOS)` section in `docs/security.md` covering quick-start, `--safe` mode, and threat model.
- **Installer post-install hint**: `render_post_install_notes()` surfaces an optional hint when `cco` is detected on `PATH`, pointing to the launcher and docs.

## [0.50.0] - 2026-04-08

### Removed

**Nuclear security cleanup**: a large pile of markdown-theater "security" features
that were never invoked, broken, or created false confidence has been deleted.
Pre-1.0 breaking change. Surviving gates: the Bash `PreToolUse` pattern check, the
spawn-session pattern check plus rate limit, the `workflow_state_save/load`
validator, and the pre-commit scanner.

- **PromptSleuth** semantic intent classification (source, tests, MCP tools,
  config keys, installer entries, DB tables `intent_checks`, `sleuth_budget`,
  `sleuth_cache`). Never reached production; depended on an uninstalled SDK path.
- **Ed25519 cryptographic provenance**: signing, verification, key generation,
  installer bootstrap, `installer/components/keys.py`, and the hook-level
  crypto gate. The gate silently blocked every call because content was never
  actually signed end-to-end. `cryptography` dropped from dependencies.
- **Canary tokens** (MCP tools, hook post-tool scanning, `canary_tokens` table,
  health check).
- **Session content accumulator** for "split injection" detection
  (`session_content_accumulator` table, MCP tools, hook writer).
- **Trust registry** (MCP tools, `trust_registry` table, hostile-marking path in
  workflow state validation, skill-level trust tier system).
- **Security event logging + dashboard + query CLI** (`security_events` table,
  `security_log_event`/`security_query_events`/`security_dashboard` MCP tools,
  `spellbook security events` CLI subcommand, admin `/api/security` routes,
  admin `/api/analytics` routes, admin dashboard security counts).
- **Spotlighting** (delimiter-based external content wrapping, hook integration,
  PR fetch wrapper, config keys).
- **Security modes** (`security_mode` table, `security_set_mode` MCP tool,
  `get_current_mode`/`should_auto_elevate` helpers, `--mode` CLI flags).
- **Input/output sanitization MCP surface** (`security_check_output`,
  `security_sanitize_input`, `do_sanitize_input`, `do_check_output`).
- **Honeypot MCP decoy tools** (`security_disable_all_checks`,
  `system_prompt_dump`, `credential_export`) — depended on deleted event logging.
- **LODO evaluation harness** (`scripts/run_lodo_eval.py`, datasets).
- **`security-trust-tiers` skill** plus all references in `AGENTS.spellbook.md`,
  README, docs, and `dispatching-parallel-agents`.
- **Installer security wizard** / `--security-level` / `--security-wizard` flags /
  `installer/components/security.py` / feature group UI.
- **`check_security_domain` health probe** (dropped from `FULL_DOMAINS`).
- Legacy `TRUST_LEVELS`, `INJECTION_TRIGGERS`, `EXFILTRATION_PATTERNS` exports.

### Changed

- **`spellbook/security/` renamed to `spellbook/gates/`** to reflect its new
  reality as pattern-based gates, not a security framework. All imports updated.
  The scanner, rules, check module, and the trimmed `do_detect_injection`
  helper move with it. `python3 -m spellbook.gates.check` is the CLI entry
  point used by the OpenCode plugin.
- **`security_check_tool_input`** is now the only remaining `security_*` MCP
  tool. It wraps the same `check_tool_input` used by the hooks.
- **`init_db`** drops the deleted tables if they exist (cleanup path for
  upgraded installs); no new CREATE TABLE statements for deleted features.
- **Surviving gates run unconditionally.** No more `security.mode`,
  `security.enabled`, `security.spotlighting.*`, `security.crypto.*`,
  `security.sleuth.*`, or `security.lodo.*` config keys.

## [0.49.0] - 2026-04-08

### Changed
- **Platform self-identification**: `spellbook_session_init` now accepts a `platform` parameter so LLMs can self-identify their platform (`claude_code`, `opencode`, `codex`, `gemini`) from their own system prompt instead of relying on environment variable detection. `AGENTS.spellbook.md` Step 0 no longer runs `env | grep` at session start.

## [0.48.0] - 2026-04-08

### Changed
- Replace `anti-ai-tone.md` with comprehensive `writing-guide.md` covering structural dead tells, human signals, sniff test, and before/after examples
- Update all references across commands, docs, and skills

## [0.47.0] - 2026-04-06

### Added
- **TTS service management**: Managed TTS service via launchd (macOS), systemd (Linux), and Task Scheduler (Windows)
- **ServiceConfig dataclass**: Parameterized service management replacing hardcoded MCP-only ServiceManager
- **Dedicated TTS venv**: Isolated virtual environment with auto-device detection (mps/cuda/cpu)
- **Lazy TTS provisioning**: `config_set` MCP tool triggers async fire-and-forget TTS provisioning
- **Eager TTS provisioning**: Installer wizard provisions TTS service during setup
- **TTS service cleanup**: Uninstaller removes TTS service, venv, and related artifacts
- **Cross-process provisioning lock**: File-based lock prevents concurrent TTS provisioning
- **`--security-wizard` flag**: Opt-in flag for `install.py` to run the interactive security feature selection wizard

### Changed
- **ServiceManager refactored**: Accepts `ServiceConfig` instead of hardcoded MCP service assumptions
- **WYOMING_DEFAULT_HOST**: Changed from `"localhost"` to `"127.0.0.1"` for IPv4 consistency
- **Installer tagline**: Updated from "Defense-in-depth security for AI coding assistants" to "Skills, commands, and MCP tools for AI coding assistants"
- **Security prompts default to silent**: The installer no longer prompts for security feature configuration during install. Recommended defaults (spotlighting=on, crypto=on, sleuth=off, lodo=on) are applied silently. Use `--security-wizard` to opt into the interactive quiz, or change settings post-install via `spellbook config set` or the admin UI.

## [0.46.2] - 2026-04-06

### Fixed
- **Installer update prompt from source repo**: Running `./install.py` from within the git repo no longer prompts "Update to latest version?" against origin/main. The installer now detects when it is being run from the source repository and skips the update check.

## [0.46.1] - 2026-04-06

### Fixed
- **Security hook false positives**: LOW-severity entropy findings (ENTROPY-001) no longer block legitimate Bash commands. The entropy check is retained as an informational signal but no longer causes `check_tool_input` or `check_tool_output` to return `safe=False`.

## [0.46.0] - 2026-04-06

### Breaking
- **TTS MCP tools renamed**: `kokoro_speak` and `kokoro_status` renamed to `tts_speak` and `tts_status`
- **TTS backend replaced**: TTS no longer uses in-process Kokoro. Requires a Wyoming protocol TTS server (e.g., wyoming-piper, wyoming-kokoro)

### Changed
- **TTS dependency group**: Now includes `wyoming`, `numpy`, `sounddevice` (removed `kokoro`, `soundfile`, `spacy`, `misaki`)
- **`TTS_DEFAULT_VOICE`**: Changed from `af_heart` to empty string (uses server default)
- **Admin frontend**: Upgraded React to v19, added `@testing-library/dom`, reverted tailwindcss v4 (requires CSS migration)
- **Brainstorming skill**: Renamed to `design-exploration`

### Added
- **Wyoming TTS config keys**: `tts_wyoming_host` and `tts_wyoming_port` for connecting to Wyoming protocol TTS servers
- **Hook config override**: `SPELLBOOK_CONFIG_PATH` env var for overriding hook config file path

### Fixed
- **Admin frontend build**: Fixed TypeScript errors from React 18/19 version mismatch and missing `@testing-library/dom` peer dep
- **Content provenance tests**: Tests no longer fail when user machine has crypto verification enabled
- **Welcome action**: Bot PRs/issues no longer trigger the first-time contributor welcome message
- **Feature-research diagram**: Improved with subgraphs, cross-references, and completion checklist

### Dependencies
- Bumped `@opencode-ai/sdk` to 1.3.13 (context-curator, workflow-state)
- Bumped `@opencode-ai/plugin` to 1.3.13 (context-curator, workflow-state)
- Bumped `typescript` to 6.0.2 (context-curator, workflow-state, spellbook-forged)
- Bumped `vitest` to 4.1.2 (tests/unit), 4.1.1 (admin frontend)
- Bumped `typescript-eslint` to 8.57.2 (admin frontend)
- Bumped `vite` to 8.0.2 (admin frontend)
- Bumped `@eslint/js` to 10.0.1 (admin frontend)

## [0.45.0] - 2026-04-06

### Added
- **Session-scoped stint support**: Stints now track behavioral mode (agent type) per session, enabling mode-aware focus context across OpenCode agent types
- **OpenCode workflow-state extension improvements**: Enhanced workflow state handling for OpenCode platform integration
- **OpencodeAgentClient test coverage**: New tests for the OpenCode agent client
- **Expanded stint test coverage**: Additional tests for stint push, pop, replace, and session-scoped behavior

### Fixed
- **OpenCode security plugin**: Removed dead `SPELLBOOK_DIR` guard that blocked the security plugin from loading when the environment variable was unset

## [0.44.0] - 2026-04-04

### Removed
- Crush platform support. Spellbook no longer installs or configures Crush (`installer/platforms/crush.py` deleted). Claude Code, OpenCode, Codex, and Gemini CLI remain supported.

## [0.43.1] - 2026-04-04

### Fixed
- **PromptSleuth installer description**: Changed "Requires an Anthropic API key" to "Requires an LLM provider (Claude Code or Gemini CLI)" since sleuth uses the unified SDK, not a direct API key
- **Dead config key**: Removed vestigial `security.sleuth.api_key` config key and default that nothing read

## [0.43.0] - 2026-04-04

### Added
- **`pr-dance` command**: New command that loops a PR through iterative CI + bot review cycles until merge-ready. Bot-agnostic with user-configurable review bot preferences stored in CLAUDE.md (project or global level)
- **"Create PR + PR dance" integration option**: Option 3 in `finishing-a-development-branch` skill creates a PR and immediately starts the PR dance loop via subagent

### Changed
- **`finishing-a-development-branch`**: Expanded from 4 to 5 options (new option 3 for PR + dance, renumbered keep/discard to 4/5)
- **`finish-branch-execute`**: Added Option 3 handler that dispatches `pr-dance` subagent after PR creation

### Fixed
- **Unified SDK wrapper**: `ClaudeAgentClient` now properly extracts `TextBlock.text` from `AssistantMessage.content` instead of storing raw content block objects. Added `on_text` streaming callback and `timeout` (default 120s) to `AgentOptions`. CLI stderr is now piped through a visible callback instead of being swallowed.
- **Diagram generation script**: Classification and patching use the fixed SDK wrapper with `on_text` streaming so AI output is visible during `generate_diagrams.py --interactive`

## [0.42.0] - 2026-04-04

### Added
- **Messaging auto-registration**: Sessions are automatically registered for cross-session messaging during `spellbook_session_init` with human-readable aliases derived from git branch/worktree context
- **Alias derivation**: Resolution order: explicit `session_name` param > git branch/worktree name (slugified, project-prefixed) > project directory basename > "session" fallback
- **Atomic collision handling**: `MessageBus.register_with_suffix()` handles alias collisions with numeric suffixes under a single lock acquisition, with session-aware compaction detection
- **Git context detection**: `detect_git_context()` utility detects branch name, worktree status, and handles detached HEAD with short commit hash fallback
- **`continuation_message` parameter**: Now wired through the `spellbook_session_init` MCP tool to the core `session_init()` function
- **Upfront installer wizard**: All configuration questions (platforms, security, TTS, profile) are now collected in a single wizard before installation begins, replacing the previous scattered prompts
- **Rich-based platform selector**: Platform selection now uses Rich panels and prompts instead of raw termios, improving Windows compatibility and visual consistency
- **Startup profiling**: Daemon startup phases are now individually timed and logged for performance visibility

### Fixed
- **Config wizard filtering bug**: `--reconfigure` security feature prompts now correctly match dotted config keys to bare feature IDs (previously always returned empty)

### Removed
- **init_curator_tables no-op**: Removed dead code from daemon startup (function was already a pass-through)

## [0.41.0] - 2026-04-04

### Added
- **Cross-session messaging**: In-memory message bus with bounded queues, direct/broadcast/reply patterns, correlation tracking with TTL sweep, and SSE real-time delivery via MessageBridge
- **Messaging MCP tools**: `messaging_register`, `messaging_send`, `messaging_broadcast`, `messaging_reply`, `messaging_poll`, `messaging_list`, `messaging_unregister` for inter-session communication
- **File-based bridge**: MessageBridge writes messages to per-alias inbox directories and polls SSE streams for delivery, enabling hook-based message injection without daemon coupling
- **Session-scoped inbox draining**: Hook `_messaging_check` only drains inboxes matching the current session ID via `.session_id` marker files

## [0.40.0] - 2026-04-04

### Removed
- **Swarm coordination subsystem**: Removed all swarm MCP tools (`mcp_swarm_create`, `mcp_swarm_register`, `mcp_swarm_progress`, `mcp_swarm_complete`, `mcp_swarm_error`, `mcp_swarm_monitor`), coordination server, protocol schemas, backend abstraction, worker contract, state manager, retry policy, and DB models
- **Session spawner**: Removed unused `spellbook/session/` package
- **Coordination backend preferences**: Removed `CoordinationBackend`, `CoordinationConfig`, and related preference types from `core/preferences.py`
- **Dashboard swarm metrics**: Removed `running_swarms` count from admin dashboard

## [0.39.0] - 2026-04-03

### Added
- **Session profiles**: 8 bundled behavioral profiles (Thought Partner, Terse, Mentor, Critic, Rubber Duck, Ship It, Architect, Quiet) that shape AI assistant tone and collaboration style per session
- **Profile selection wizard**: Installer and `--reconfigure` offer profile selection during setup; selected profile injected into sessions via `session_init`
- **Profile auto-discovery**: Profiles from `profiles/` directory with custom overrides from `~/.local/spellbook/profiles/`
- **Headless session spawning**: `spawn_session` defaults to subprocess mode (`claude -p`) instead of opening a terminal window; supports `allowed_tools` and `disallowed_tools` for tool restriction
- **Hook error logging**: Errors in `spellbook_hook.py` logged to `~/.local/spellbook/logs/hook-errors.log` with 1MB rotation and 3 backups

### Changed
- **Hooks use daemon venv Python**: Hook commands now invoke the daemon venv interpreter instead of system Python, ensuring all spellbook dependencies are available
- **Security gates fail-closed**: Hook security gates exit with code 2 when the security module is unavailable, with diagnostic logging
- **Fractal error messages**: Validation errors for `intensity` and `checkpoint_mode` now list valid options
- **Skill documentation**: Added valid parameter values for fractal intensity/checkpoint_mode and roundtable stage/archetypes to skill and command descriptions

### Fixed
- **Installer daemon progress**: Moved progress display initialization before daemon install so "Starting daemon..." appears during the venv build and health-check loop instead of a blank pause
- **Reconfigure config persistence**: `--reconfigure` in both `install.py` and CLI now correctly persists config wizard selections (previously discarded)
- **Security module imports**: Moved DB-dependent imports in `security/check.py` from module level into functions to avoid requiring `aiosqlite` at import time
- **bigfoot 0.19.1 compatibility**: Migrated ~20 test files from bigfoot sandboxes to monkeypatch for subprocess/socket/database interception compatibility

## [0.38.0] - 2026-03-28

### Added
- **`documenting-projects` skill**: Publication-ready documentation generation with Diataxis framework enforcement and adaptive tone profiles
- **5 new commands**: `/docs-audit`, `/docs-plan`, `/docs-write`, `/docs-review`, `/write-readme` for structured documentation workflows
- **Anti-AI-tone rules**: 23+ banned phrases enforced across all documentation output
- **Build tooling auto-detection**: Automatic discovery of MkDocs, Sphinx, and Docusaurus configurations
- **8 measurable quality criteria** for documentation review scoring
- **Standalone `/write-readme` command** for lightweight README generation without full docs workflow

## [0.37.1] - 2026-03-27

### Changed
- **Testing framework**: Migrated entire test suite (99 files, 4822 tests) from `unittest.mock` to bigfoot
  - Strict sandbox enforcement: every external call must be pre-authorized
  - Every mock interaction must be asserted (catches unused mocks)
  - Guard mode prevents real I/O by default (subprocess, HTTP, database blocked unless explicitly allowed)
- Added `dirty-equals` to dev dependencies for flexible assertion matching

## [0.37.0] - 2026-03-24

### Added
- **Installer renderer abstraction** (`installer/renderer.py`): `InstallerRenderer` ABC with `RichRenderer` (wraps existing TUI) and `PlainTextRenderer` (no Rich dependency) implementations, enabling non-TTY and CI environments
- **Installer CLI flags**: `--security-level {minimal,standard,strict}`, `--no-tts`, and `--reconfigure` for non-interactive and upgrade workflows
- **Config introspection helpers** (`spellbook/core/config.py`): `config_is_explicitly_set()` and `get_unset_config_keys()` for flat dotted-key config lookup
- **Unified Agent SDK** (`spellbook/sdk/unified.py`): Single programmatic interface for Claude and Gemini agents, built on `claude-agent-sdk`
- **Tooling discovery registry** (`spellbook/tooling/index_registry.py`): Indexed MCP tool registry for faster lookups
- **Multi-provider diagram generation**: `generate_diagrams.py` updated to produce architecture diagrams for all supported platforms
- **Installer renderer and config helper tests**: 24 new tests across `test_installer_renderer.py` and `test_installer_config_helpers.py`
- **Unified SDK tests**: Unit tests in `tests/unit/test_unified_sdk.py`

### Changed
- **Installer entry points wired through renderer**: Both `install.py` and `spellbook/cli/commands/install.py` now create a renderer (auto-detecting TTY) and pass it to `Installer.run()` instead of calling `tui.py` directly
- **Platform support documentation**: Claude Code marked as primary platform; OpenCode, Codex, Gemini CLI, Crush marked as basic support across README, AGENTS.md, and platform docs
- **Skill documentation optimized**: Reduced token usage in dehallucination, writing-skills, and using-skills skill docs
- **Tooling discovery refactored**: Enhanced `spellbook/tooling/discovery.py` with registry-backed lookups

### Fixed
- **AsyncMock test failures**: 4 tests in `test_diagram_update.py` used `MagicMock` for async `generate_diagram()`, causing `TypeError` on `await`

## [0.36.0] - 2026-03-24

### Added
- **Runtime injection defense**: 5 concentric defense layers for external content: spotlighting boundary marking, session content accumulator, LODO-evaluated regex detection, PromptSleuth semantic intent classification, and Ed25519 cryptographic content provenance
- **Rich TUI installer** (`installer/tui.py`): Interactive terminal UI with platform selection checkboxes, security feature configuration, and key generation progress display
- **6 new MCP security tools**: `security_check_intent`, `security_sign_content`, `security_verify_signature`, `security_accumulator_write`, `security_accumulator_status`, `security_sleuth_reset_budget`
- **4 new database tables**: `intent_checks`, `session_content_accumulator`, `sleuth_budget`, `sleuth_cache`
- **LODO evaluation framework**: Leave-One-Dataset-Out testing for regex detectors with 4 curated attack datasets (AdvBench, BIPIA, HarmBench, InjecAgent)
- **Ed25519 key management**: Key generation, rotation with archive support, auto-signing of trusted files during installation
- **Spotlighting integration**: PostToolUse hook auto-wraps external content; `pr_fetch` wraps PR diffs
- **Content accumulator hook**: PostToolUse auto-records external content fragments for split injection detection
- **`cryptography` and `rich` dependencies** for crypto provenance and TUI

### Fixed
- **WebSearch missing from security_tools set**: PostToolUse security scanning now covers WebSearch results

### Changed
- **Crypto provenance defaults to opt-in**: Disabled by default, enabled by the TUI installer after successful key generation

## [0.35.2] - 2026-03-21

### Fixed
- **Security page severity counts**: Summary cards showed 0 for Critical/Warning/Info due to case mismatch (backend returns uppercase, frontend looked up lowercase)

## [0.35.1] - 2026-03-21

### Changed
- **Stint system redesign**: Stints are now LLM-owned attention declarations, not auto-generated tool call traces
- **Simplified stint entry schema**: Removed `type`, `parent`, `exited_at`, `success_criteria` fields from new entries
- **Admin stacks page**: Removed type badge and type column; depth gauge max changed from 8 to 6

### Added
- **Depth cap**: Hard limit of 6 on stint stack depth in `push_stint`
- **Empty-stack nudge**: Depth check now returns a nudge when no focus is declared
- **Staleness warnings**: Entries older than 4 hours are flagged in depth check output
- **Focus Tracking guidance** in `AGENTS.spellbook.md` explaining stint ownership model
- **One-time cleanup script** (`scripts/reset_bloated_stints.py`) for resetting bloated stacks

### Removed
- **`_stint_auto_push` hook**: No longer auto-pushes stints on Skill tool invocations (root cause of unbounded stack growth)
- **`success_criteria` parameter** from `stint_push` MCP tool

## [0.35.0] - 2026-03-21

### Added
- **Auto-memory bridge hook**: Intercepts Claude Code Write tool calls to `~/.claude/projects/*/memory/` paths and mirrors content into spellbook's structured memory via new `/api/memory/bridge-content` endpoint
- **Bridge content endpoint** (`/api/memory/bridge-content`): Dual-event storage with brief summary for consolidation pipeline + full content for audit trail
- **MEMORY.md bootstrap regenerator** (`spellbook/memory/bootstrap.py`): Generates static redirect template instructing the model to use spellbook MCP memory tools
- **Session init memory integration**: Refreshes MEMORY.md on every new session start via `spellbook_session_init`
- **Memory System section** in `AGENTS.spellbook.md` supplementing Claude Code auto-memory with spellbook MCP tool preferences
- **ErrorBoundary** component wrapping all admin page routes to catch render crashes with error display and retry
- **ErrorDisplay** component for admin data fetch failures with retry button
- **`--stamp` flag** for `generate_diagrams.py` to skip diagram generation and just update hashes
- **Worktree Dispatch Preamble** in dispatching-parallel-agents skill enforcing 5-step verification for subagent worktree work

### Fixed
- **Stacks page blank render**: Hook extracted `.stacks` instead of `.items` from API response
- **Config nav position**: Moved to second item (right after Dashboard)
- **Corrections header height**: Filter buttons moved from header to content area for consistent header sizing across pages
- **Worktree dispatch instructions**: Subagent prompts now require explicit path/branch verification before any work

## [0.34.0] - 2026-03-20

### Added
- **Fractal explorer redesign**: two-view layout with full-width data table (list view) and dedicated details pane (graph view)
- **GraphTable component**: sortable columns (seed, status, intensity, nodes, project dir, created, updated), text search, status filter, project dir filter, pagination
- **Breadcrumb navigation**: `// FRACTAL // Graph "seed..." // Node #id // Chat Log` with clickable segments
- **`project_dir` column** on fractal graphs table (v3-to-v4 schema migration), exposed in list API with filtering support
- **Fractal list API enhancements**: `search`, `sort_by`, `sort_order`, `project_dir` query params; `updated_at` in response
- **PageHeader and PageLayout components**: shared layout primitives for consistent headers across all admin pages
- **Dashboard improvements**: per-database health indicators, top 5 tools with analytics summary, session count from actual conversation files

### Changed
- All 12 admin pages migrated to shared PageLayout component for consistent `// PAGE_NAME` headers and spacing
- Dashboard session count now scans `~/.claude/projects/*.jsonl` files instead of querying transient `souls` table
- Dashboard Event Bus section collapsed to single compact row
- Analytics page period selector styled as inline text toggles

### Fixed
- Dashboard showing 0 sessions (was querying wrong data source)

## [0.33.0] - 2026-03-19

### Added
- **Develop skill execution model redesign**: dialectic validation (none/roundtable) and token enforcement (work-item/gate/every-step) are now independent user preferences, configurable in Phase 0.4
- **Scope drift detection**: re-evaluation checkpoints in Phase 1.5 discovery catch when user answers expand scope beyond the classified complexity tier. New `SCOPE_EXPANSION` ARH response type, `evaluate_scope_drift()` detection function, and 12th completeness validation function (`scope_consistent_with_tier`)
- **Dispatch enforcement**: CRITICAL blocks and post-gate verification on all 8 Phase 4 subagent dispatch points. Three new anti-rationalization patterns: Gate Elision, Self-Review Substitution, Momentum Preservation
- **Roundtable 3-archetype fast mode**: `GATE_ARCHETYPES` constant maps each quality gate to a 3-archetype subset (Justice always included as arbiter). `get_gate_archetypes()` function for quality gate validation
- **Gate completion tracking**: `gate_completions` table in forged.db, `forge_record_gate_completion` MCP tool, auto-recording on roundtable consensus
- **Dependency enforcement**: `forge_iteration_start` checks project graph for incomplete `depends_on` features before issuing tokens, returns per-dependency status on block
- **Required `gate` and `feature_name` parameters** on `roundtable_convene` and `process_roundtable_response` for explicit gate identification
- `spellbook` CLI with 10 command groups: doctor, server, install, update, admin, config, memory, session, security, events
- Three-layer package architecture: core -> domains -> interfaces
- `websockets` dependency for CLI streaming
- `spellbook/mcp/__main__.py` entry point for `python -m spellbook.mcp` daemon execution

### Changed
- **Work decomposition is now transparent**: orchestrator decides based on plan structure and context budget, replacing the rigid COMPLEX/swarmed execution model. Work-item prompt files replace work packets
- Package renamed from `spellbook_mcp` to `spellbook`
- server.py (3,945 lines) decomposed into mcp/server.py + 13 tool files + routes
- Daemon installer calls `install_service()` directly instead of spawning `scripts/spellbook-server.py` subprocess
- Diagram freshness checking hashes heading structure instead of full content (ignores frontmatter changes), pre-commit hook scoped to staged files only
- All roundtable callers updated for required `gate` parameter, including OpenCode extension (pre-existing broken caller fixed)

### Deprecated
- `autonomous-roundtable` skill (absorbed into develop; migration guide provided)
- "Forge" as a user-facing workflow concept (forge_* MCP tool namespace preserved for backward compatibility)
- `spellbook_mcp` package name (backward compat shim provided, will be removed next release)
- `SPELLBOOK_MCP_*` environment variables (use `SPELLBOOK_*` instead)

### Removed
- `scripts/spellbook-server.py` deprecated wrapper (daemon management via `spellbook server <command>` or direct `install_service()` call)
- Swarmed execution mode and work packet generation (replaced by work-item prompt files)
- Token estimation math in Phase 3.4.5 (replaced by plan-structure-based decomposition)

### Fixed
- Installer crash when `spellbook` package not yet pip-installed (handle missing metadata in `__init__.py`)
- Daemon not starting after package reorg (missing `__main__.py`, wrong module path in launchd/systemd service files)
- Daemon installer output leaking raw `print()` into formatted installer output
- `spellbook doctor` test monkeypatching wrong module (command module vs source module)
- Windows test failures: `HOME` vs `USERPROFILE`, hardcoded Unix paths, hardcoded `/tmp`

## [0.32.1] - 2026-03-18

### Fixed
- **README rewrite**: Fact-checked all claims, fixed skill count (55->56), command count (90->91), tarot archetype count (four->ten). Removed nonexistent `[admin]` pip extra and `spellbook admin open` CLI command. Rewrote tone from marketing-speak to relaxed and explanatory.
- **Citation corrections**: Fixed ICML 2025 paper attribution from "Raghunathan" to "Nagarajan et al." with correct title "Roll the dice & look before you leap" across README, AGENTS.spellbook.md, citations.md, fun-mode skill, and generated docs. Fixed Zheng caveat from "objective/STEM tasks" to "factual question-answering".
- **CVE descriptions**: All 4 CVEs in SECURITY.md and docs/security.md were mischaracterized. Corrected: CVE-2025-53967 (command injection in Figma MCP), CVE-2025-66414 (DNS rebinding in TS SDK), CVE-2025-66416 (DNS rebinding in Python SDK), CVE-2025-59536 (code injection in Claude Code startup).
- **Dead links**: Removed Trail of Bits and Embrace The Red blog URLs (404s) from docs/security.md source citations.
- **CHANGELOG corrections**: Fixed references to nonexistent `spellbook admin open` and `[admin]` extra in 0.32.0 entry. Fixed tarot "four core personas" to "ten archetypes".
- **THIRD-PARTY-NOTICES**: Reconciled with README acknowledgments table. Added derived commands (verify, systematic-debugging), noted executing-plans incorporates subagent-driven-development content.
- **Platform docs**: Replaced vague Gemini CLI limitations with specific details (no Task tool, native skills pending upstream). Added Crush to installation platform detection table and --platforms option.
- **Porting guide**: Removed emotional manipulation language ("important to my career", "take a deep breath", "believe in your abilities") while preserving all technical content.
- **AGENTS.spellbook.md**: Selective trim of most performative language ("viscerally uncomfortable", "debate fiercely", "zen master") while keeping behavioral rules.
- **Architecture docs**: Updated MCP server tool listing from outdated 5-tool list to accurate 15-category overview of 100+ tools. Fixed swarm tool names.
- **Contributing docs**: Aligned test commands with actual convention (`uv run pytest tests/` not split unit/integration).

## [0.32.0] - 2026-03-18

### Added
- **Zeigarnik focus-tracking system** - Stint stack tracks nested units of work with entry context, reminds the LLM to stay on task via depth-triggered heuristics (configurable threshold, default 5), and lets the LLM correct tracked state. Four MCP tools: `stint_push`, `stint_pop`, `stint_check`, `stint_replace`. Correction events logged for analytics (MCP-wrong vs LLM-wrong classification).
- **Unified Python hook** - Single `spellbook_hook.py` replaces all 12 individual shell hooks, reducing per-tool-call process spawns from up to 7 to 1. Security gates (bash-gate, spawn-guard, canary-check, state-sanitize) remain fail-closed; all other handlers (memory, TTS, notifications, audit) are fail-open. Windows parity via `spellbook_hook.ps1` wrapper.
- **Stint auto-push for skills** - PreToolUse hook automatically pushes a stint when a Skill tool is invoked, tracking skill invocations without requiring explicit LLM cooperation.
- **Stint compaction survival** - Pre-compact hook saves stint stack to workflow state; post-compact hook restores it via `stint_replace`, preserving focus context across context resets.
- **Behavioral mode preservation** - Stint entries carry a `behavioral_mode` field (e.g., "ORCHESTRATOR: delegate via subagents") that survives compaction and gets re-injected via depth check reminders and post-compact recovery. Auto-populated from `<BEHAVIORAL_MODE>` tags in SKILL.md files.
- **Smart diagram updates** - `generate_diagrams.py` now classifies source changes before deciding how to update diagrams: non-structural changes are stamped fresh without regeneration, small structural changes trigger surgical patching, and only major restructures trigger full regeneration. Uses haiku model for fast classification. Interactive mode shows classification with Enter-to-accept defaults.

### Fixed
- **Recovery directive skill constraint fetch** - `_build_recovery_directive` used wrong dict keys (`found`/`constraints` instead of `success`/`content`) when fetching skill constraints, so FORBIDDEN/REQUIRED sections were never included in post-compaction recovery.

### Changed
- **Hook installer upgrade path** - Installing spellbook now removes old individual shell hook entries from `settings.json` and registers the unified hook. User-defined hooks are preserved.
- **Renamed `implementing-features` skill to `develop`** - Shorter, more descriptive name. Applied via `scripts/rename_skills.py` across 100 files (skills, commands, docs, diagrams, tests, Python backend). Old name no longer exists; all references updated.
- **Removed `receiving-code-review` skill** - Deprecated skill removed along with all references. Functionality consolidated into code-review `--feedback` mode.

### Added
- **Web admin interface** - Browser-based admin UI served from the MCP daemon at `/admin`. Provides real-time observability and management across all spellbook subsystems.
  - **Dashboard** with health status, subsystem metrics, and live activity feed
  - **Memory browser** with full-text search, CRUD operations, and consolidation trigger
  - **Security event log** with severity/type/date filtering and summary aggregation
  - **Session viewer** scanning Claude Code JSONL session files with project filtering and expandable detail
  - **Config editor** with toggle switches for boolean settings, inline editing, and default value rendering
  - **Fractal graph explorer** with interactive Cytoscape.js visualization, depth filtering, node detail panels, chat log viewer, and viewport persistence in URL params
  - **Tool call analytics** dashboard mining security_events for tool frequency, error rates, and usage timeline with period filtering
  - **Subsystem health matrix** showing vital signs across all 4 SQLite databases with status badges, row counts, and last activity
  - **Event bus live monitor** with real-time WebSocket event stream, subsystem filtering, auto-scroll, and event detail expansion
  - **WebSocket event streaming** with ticket-based auth, auto-reconnect, and shared connection via React Context
  - **Asyncio event bus** with bounded per-subscriber queues and thread-safe `publish_sync()` for MCP handlers
  - **Pull-based MCP notification queue** with broadcast/namespace/session scoping
  - Admin dashboard accessible at `http://localhost:8765/admin/` when MCP server is running
  - Auth: SHA-256 signed HTTP-only cookies, WebSocket ticket exchange, token-based session management
  - Tech: FastAPI sub-app mounted via `_additional_http_routes`, React 18 + TypeScript + Vite 5 + Tailwind 3
  - Admin frontend bundled with MCP server
  - **Focus tracking admin page** showing per-project stint stacks with depth gauge, correction event log with filtering, and dashboard summary card
  - **Session detail view** with full metadata display (ID, project, slug, title, timestamps, message count, size, first user message) and paginated **chat history viewer** rendering 10+ JSONL message types with type-based visual styling. Both pages separately linkable via `/sessions/:project/:id` and `/sessions/:project/:id/chat`
  - **Session multi-select filter** with checkbox dropdown for filtering by multiple projects simultaneously, plus free-text search across session content
  - **Spellbook branding** throughout admin: book-with-sparkle favicon, sidebar icon, sparkle loading spinner, login page icon
  - **Admin documentation** with screenshots of all 11 pages, added to mkdocs site and README
  - **`[docs]` optional extra** with mkdocs-material, mike for building documentation locally
  - **Version display** in sidebar footer showing running spellbook version
  - **Event monitor with history** - REST endpoint for recent events plus live WebSocket stream; event publishing from security, memory, stint, and fractal MCP handlers
  - **Login page** with MCP token authentication and SHA-256 signed HTTP-only session cookies
  - **Platform compatibility docs** noting Claude Code JSONL session dependency, welcoming contributions for other platforms
  - **`--no-admin` installer flag** to skip admin frontend dependencies; frontend build staleness check via pre-commit hook
- **"Signature Spells" in README and docs** - Five highlighted skills (develop, fractal-thinking, auditing-green-mirage, fact-checking, advanced-code-review) featured as signature capabilities
- **Docs restructuring** - New task-oriented Guide section with curated skill selections, flattened reference navigation, intro paragraphs on guide-listed skill docs pages
- **Quickstart rewrite** - Leads with `develop` skill workflow, links skill names to docs pages, removes outdated design-explore/plan/execute sequence
- **Installer WHAT'S NEW display** - Shows changelog entries for new versions during upgrade
- **Fractal session backfill script** (`scripts/backfill_fractal_sessions.py`) - Populates `session_id` and `timestamp` on existing fractal graph nodes by scanning JSONL session transcripts
- **Shared diagram config** (`scripts/diagram_config.py`) - Centralized exclusion lists, aliases, and tiering config for diagram generation, freshness checking, and docs completeness
- **Bulk skill rename script** (`scripts/rename_skills.py`) - Automates full-codebase skill renames with regex word-boundary protection, specificity ordering, dry-run mode, and `git mv` integration
- **Diagram stamp mode** - `check_diagram_freshness.py --stamp` updates source hashes in diagram metadata without regenerating content

### Fixed
- **Compaction detector missed all compaction events** - `check_for_compaction()` checked `msg.get('type') == 'summary'` but Claude Code marks compaction with `isCompactSummary: true` on `type: "user"` messages. 47 compacted sessions across projects were going undetected, leaving the souls table empty.
- **Broken test import in test_check_tool_input_mcp.py** - `from conftest import get_tool_fn` failed with `ModuleNotFoundError` because pytest conftest modules aren't directly importable from subdirectories. Added `tests/` to `sys.path` so the import resolves correctly.

## [0.30.5] - 2026-03-12

### Fixed
- **MCP auth: hooks sent unauthenticated requests** - All hooks that call the MCP daemon's REST API (`memory-capture`, `memory-inject`, `tts-notify`, `pre-compact-save`, `post-compact-recover`) were missing the `Authorization: Bearer` header, causing 401 Unauthorized on every request. Both bash and PowerShell variants now read the token from `~/.local/spellbook/.mcp-token`.
- **MCP auth: token regenerated on every daemon restart** - `generate_and_store_token()` generated a fresh random token on each startup, invalidating any previously registered auth headers in Claude Code configs. Now reuses the existing token from disk if present, only generating on first install.
- **MCP registration: auth header missing from `.claude.json`** - The spellbook MCP entry in `.claude.json` had no `headers` field, so Claude Code sent unauthenticated requests to the daemon. The installer now passes `--header "Authorization: Bearer <token>"` during registration.
- **MCP registration: non-default config dirs ignored** - `register_mcp_http_server()` always targeted the default `~/.claude` config. Added `config_dir` parameter so the installer correctly registers for each target config directory (e.g., `~/.claude-work`).
- **Docker test collection error** - `tests/docker/test_bootstrap.py` failed to collect due to missing `tests/__init__.py` needed for the `from tests.docker.conftest import ...` import.

## [0.30.4] - 2026-03-12

### Changed
- **Removed outdated platform support tables** from README and docs index.

## [0.30.3] - 2026-03-12

### Fixed
- **MCP registration arg ordering** - `claude mcp add`'s `--header` option is variadic and was consuming positional arguments (`name`, `url`) when placed before them, causing "missing required argument 'name'" errors. Moved `--header` after positional args to match CLI's documented usage. Also added `-s user` scope to `claude mcp remove` calls so they correctly target user-scoped registrations.

## [0.30.2] - 2026-03-11

### Fixed
- **MCP auth header missing from installer** - The MCP server requires bearer token authentication, but `register_mcp_http_server` and all platform installers omitted the `Authorization` header when registering the server. Clients received 401 Unauthorized on every request. All platforms (Claude Code, OpenCode, Codex, Crush) now read the token from `~/.local/spellbook/.mcp-token` and include it in the MCP registration.

## [0.30.1] - 2026-03-10

### Fixed
- **Database migration for branch column** - Existing installations crashed on daemon startup because the new `branch` column was missing from the `memories` table. Added `ALTER TABLE` migration that checks for the column before creating the index.

## [0.30.0] - 2026-03-10

### Added
- **Branch-aware memory system** - Memories are now scoped to the git branch where they were created. Recall scoring boosts memories from the current branch (1.5x) and ancestors (1.2x), penalizes unrelated branches (0.8x). Two-phase scoring: SQL over-fetch with base score, then Python re-rank with ancestry-aware multipliers via `git merge-base --is-ancestor`. New `branch_ancestry` module with LRU-cached ancestry checks. New `memory_branches` junction table for M:N branch-memory associations.
- **Namespace unification** - Worktrees now resolve to the main repository root for consistent project identification. New `resolve_repo_root()` in `path_utils` uses `git worktree list --porcelain` to find the main worktree.

### Fixed
- **Windows path handling** - `resolve_repo_root` now normalizes git output with `os.path.normpath` so paths use OS-native separators. `encode_cwd` handles both backslash and forward slash separators. Bash hook tests skip on Windows.

## [0.29.0] - 2026-03-09

### Added
- **Fractal-thinking integration for roundtable ITERATE path** - When a roundtable returns ITERATE with escalation conditions (2+ iterations on same stage or 2+ blocking-severity items), `reflexion-analyze` now invokes fractal-thinking for deep exploration before retrying. New `fractal_feedback` module maps fractal harvest output to Feedback instances. Enhanced `_determine_return_stage()` with fractal-informed stage recommendations and distance-based confirmation guardrails. Simple/first-time ITERATEs continue using plain reflexion with zero overhead.
- **Explicit memory integration in Tier 1 skills** - Added `memory_recall` calls at investigation/decision start points and `memory_store_memories` calls at key output moments in 5 skills: verifying-hunches, debugging, implementing-features, code-review, and advanced-code-review. Closes the learn-and-recall loop that was previously limited to passive file-path auto-injection via hooks.

## [0.28.1] - 2026-03-09

### Fixed
- **Update checker no longer falls back to unreleased versions** - When the GitHub releases API is unavailable (no `gh` CLI or network failure), the update checker now reports no update instead of falling back to `git show origin/main:.version`, which would include unreleased and pre-release versions.

## [0.28.0] - 2026-03-09

### Changed
- **Consolidated verification skill hardening** - Hardened fact-checking, devil's advocate, and dehallucination skills with shared evidence hierarchy (6 tiers from code trace to LLM knowledge), mandatory depth escalation protocol (shallow/medium/deep), and 6 mandatory Inconclusive conditions. Devil's advocate now uses READY/NEEDS WORK/NOT READY/INCONCLUSIVE verdicts instead of hardcoded issue minimums. Added two new implementing-features phases: Phase 1.5.7 (Dehallucination Gate) and Phase 2.5 (Assumption Verification). Created shared reference at `skills/shared-references/evidence-hierarchy.md`.

## [0.27.0] - 2026-03-09

### Changed
- **Memory consolidation refactor** - Replaced LLM-based memory consolidation with four heuristic strategies (content-hash dedup, Jaccard word similarity, tag grouping, temporal clustering). Removed `anthropic` from production dependencies. Added two new MCP tools (`memory_get_unconsolidated`, `memory_store_memories`) for optional client-side LLM synthesis.

### Fixed
- **Daemon PATH detection** - Resolve CLI tool paths at install time via `shutil.which()` so tools installed through mise, asdf, and other version managers are found by the daemon.
- **Update checker** - Use GitHub releases API instead of `git show origin/main:.version` to determine latest version, which naturally excludes pre-releases and drafts.
- **Pre-release workflow** - Auto-release now creates pre-releases by default so releases can be reviewed before promotion.

## [0.26.0] - 2026-03-08

### Added
- **MCP server security hardening** - Comprehensive security hardening based on 45-source audit covering industry CVEs, OWASP agentic security guidance, and MCP-specific attack research. Fixes 13 identified vulnerabilities including an RCE kill chain through workflow state, command injection in terminal construction, and injection via DB-sourced recovery context. Adds bearer token authentication for HTTP transport via FastMCP middleware, connection health checks with TTL, boot prompt validation with context-aware parsing, Shannon entropy detection for obfuscated payloads, and path traversal protection for spawn sessions. Removes permissive security mode entirely. Includes SECURITY.md with threat model and responsible disclosure policy. ([45 cited sources](docs/security.md))
- **Memory system** - Project-scoped knowledge persistence with FTS5 search, namespace isolation, and importance scoring. Memories are stored in the spellbook database and recalled across sessions.

## [0.25.1] - 2026-03-07

### Fixed
- **polish-repo-community: avoid content filter on CODE_OF_CONDUCT.md** - The Contributor Covenant full text contains policy language that triggers API content filtering (400 errors). The skill now prefers fetching the canonical file via curl, falls back to a short linking stub, or directs users to GitHub's built-in generator.

## [0.25.0] - 2026-03-06

### Changed
- **Installer output redesign** - Prettier terminal output with box-drawing section headers, unicode tree characters (`├─`/`└─`) for hierarchy, consistent status icons (`✓`/`→`/`⊘`/`✗`), elapsed time display, and no double blank lines. Fixed double banner on uv re-execution and platform counter bug. Added UTF-8 stdout/stderr reconfiguration for Windows compatibility.
- **Rename project-presence to polish-repo** - All skills, commands, and docs renamed from `project-presence-*` to `polish-repo-*` for easier recall.
- **Expand community engagement guidance** - Added concrete brainstorming sources (README gaps, architectural debt, ecosystem integrations, etc.) for contributor magnets and conversation starters in the polish-repo-community command.

## [0.24.0] - 2026-03-06

### Added
- **polish-repo skill** - New skill for improving open source project discoverability and presentation without relying on social media. Includes 5 phase commands covering README authoring (scratch/improve/replace), naming workshops, visual identity briefs, community infrastructure, and a 100-point audit scoring rubric. Based on analysis of 50+ open source projects across Python, Go, JS, and Rust ecosystems.
- **Community infrastructure** - Issue templates (bug report + feature request) using GitHub YAML form format, lightweight PR template, CONTRIBUTING.md with dev setup and skill authoring guide, SECURITY.md with spellbook-specific vulnerability scope, and a welcome bot GitHub Action for first-time contributors.
- **GitHub topics** - Added 15 topics for discoverability (ai-assistant, claude, mcp, python, etc.)
- **Homepage URL** - Set to docs site for repo metadata completeness.

## [0.23.0] - 2026-03-05

### Changed
- **Replace encyclopedia with AGENTS.md project knowledge** - The encyclopedia concept (`~/.local/spellbook/docs/<project>/encyclopedia.md`) is replaced by standard `AGENTS.md` files within project repositories. AGENTS.md is version-controlled, benefits all contributors, and uses the standard Claude Code convention. Session start now checks for AGENTS.md instead of encyclopedia.
- **Expand opportunity awareness** - Agents now also watch for project knowledge candidates (undocumented conventions, build commands, gotchas) and suggest adding them to AGENTS.md.
- **Update spellbook AGENTS.md** - Added quick-start commands, key conventions, pre-commit hook guidance, and architecture notes for AI assistants working on the spellbook repo itself.

### Deprecated
- **project-encyclopedia skill** - Use AGENTS.md files instead. Will be removed in a future version.
- **encyclopedia-build command** - Use AGENTS.md files instead. Will be removed in a future version.
- **encyclopedia-validate command** - Use AGENTS.md files instead. Will be removed in a future version.

## [0.22.0] - 2026-03-05

### Added
- **Skill Opportunity Awareness** (`AGENTS.spellbook.md`) - Agents now self-monitor for reusable patterns during work and suggest skill, command, or agent candidates at natural pause points. Includes subagent observation convention (`## Skill Observations` output section) for bubbling up discoveries from subagents to the orchestrator.

## [0.21.0] - 2026-03-05

### Removed
- **Nim hook compilation system** - Removed the 3-tier hook dispatch (Nim > .py > .sh) in favor of a simpler 2-tier system (.sh on Unix, .ps1 on Windows). The `_SHELL_TO_NIM_BINARY` mapping, `nim_available` parameter threading, and `_compile_nim_hooks()` build step are all gone.
- **Python hook wrappers** - Removed all 10 `.py` hook files from `hooks/`. These were intermediate wrappers that called security check modules; the new `.sh` and `.ps1` hooks call them directly.
- **Nim source directory** - Deleted `hooks/nim/` (Nim sources, build config, and codegen).
- **Nim test files** - Deleted `test_nim_hook_binaries.py` and `test_nim_codegen.py`.

### Added
- **PowerShell hooks** - 10 new `.ps1` hooks mirroring every `.sh` hook for native Windows support. Security hooks are fail-closed (exit 2 on error); audit, notification, and compaction hooks are fail-open (exit 0 on error).
- **Legacy hook cleanup** - `_cleanup_legacy_hooks()` automatically removes stale Nim binary and `.py` wrapper entries from `settings.json` during install, preventing conflicts with the new hook paths.

## [0.20.0] - 2026-03-05

### Added
- **System notification support** (`spellbook/notify.py`) - Native OS notifications as a visual/accessibility alternative to TTS. Fires macOS Notification Center, Linux `notify-send`, or Windows PowerShell toast when tools exceed a configurable threshold (default 30s). Platform detection handles containers, SSH/headless sessions, and Wayland desktops.
- **Notification MCP tools** - `notify_send`, `notify_status`, `notify_session_set`, `notify_config_set` for manual notifications, availability checking, and per-session or persistent configuration.
- **PostToolUse notification hooks** (`hooks/notify-on-complete.{sh,py}`) - Separate hooks that call platform notification tools directly (no HTTP round-trip, unlike TTS). Independent lifecycle, threshold, and blacklist from TTS hooks.
- **Dual PreToolUse timer files** - `tts-timer-start` hooks now write both `/tmp/claude-tool-start-{id}` (TTS) and `/tmp/claude-notify-start-{id}` (notifications), eliminating race conditions between async hooks.
- **Notification configuration** in `config_tools.py` - Session state (`notify` key), persistent config (`notify_enabled`, `notify_title`), and `SPELLBOOK_NOTIFY_THRESHOLD` / `SPELLBOOK_NOTIFY_ENABLED` environment variables for hook control.
- **Notification test suite** - 76 tests across 4 files: core module, config integration, MCP tools, and hook behavior.

## [0.19.0] - 2026-03-04

### Added
- **Crystallized v2 outputs** - All skills, commands, patterns, agents, and root documents (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.codex/spellbook-bootstrap.md`, `spellbook/coordination/WORKER_CONTRACT.md`) crystallized to v2 format. Each output verified by adversarial gap analysis before acceptance. FAIL verdicts (CRITICAL or HIGH findings) trigger source-level fixes before the crystallized output is accepted.
- **`skills/reviewing-prs`** - New skill: safe PR review protocol that detects whether the reviewing agent is working in the PR branch (`LOCAL_FILES` mode) or needs a diff-only context block (`DIFF_ONLY` mode), with mandatory injection template for subagent dispatch.

### Changed
- **Crystallize pipeline: compress-first ordering** (`commands/crystallize.md`) - Phase 3 now compresses aggressively first to establish a tight baseline before filling gaps. Previously, improvement design preceded compression, producing net-additive outputs. MEDIUM/LOW gap fills must be net-neutral (offset by equal compression); only CRITICAL/HIGH gaps may add net content.
- **Crystallize calibration preservation rule** (`commands/crystallize.md`) - Preserving calibration content means preserving the identified failure mode and correction, not the word count. A 3-sentence note condensed to 1 sentence that still names the failure mode is acceptable.
- **TDD skill sharpened** (`skills/test-driven-development/SKILL.md`) - Exceptions block clarifies "no human available? default: apply TDD". Mock rationale expanded: "unavoidable = external I/O, time, hardware -- not laziness". REFACTOR completion criteria added.
- **Multiple skills compressed and tightened** - `skills/advanced-code-review`, `skills/auditing-green-mirage`, `skills/debugging`, `skills/dispatching-parallel-agents`, `skills/fixing-tests`, `skills/generating-diagrams`, `skills/implementing-features`, `skills/writing-skills`, `commands/advanced-code-review-verify`, `commands/code-review-give`.

## [0.18.0] - 2026-03-02

### Added
- **Full Assertion Principle** (`patterns/assertion-quality-standard.md`) - New foundational rule: ALL assertions must be full, for ALL output regardless of whether it is static or dynamic. Tests MUST assert exact equality against the complete expected output. For dynamic content, construct the expected value dynamically and assert `==`; do not use partial checks. `assert "substring" in result` is BANNED unconditionally. No exceptions. Added as Invariant Principles #1 and #2, with new sections for Mock Call Assertions and Side Effects. Previously introduced as "Deterministic Output Principle" (too narrow; renamed and expanded).
- **Mock call assertion enforcement** (`patterns/assertion-quality-standard.md`) - When a dependency is mocked, tests MUST assert EVERY call with ALL arguments and verify call count. `mock.ANY` is BANNED -- construct the expected argument dynamically if needed. `assert_called()` without argument verification is BANNED. Partial mock assertion (asserting only some calls, or some args) is BANNED.
- **Side effects assertion requirement** (`patterns/assertion-quality-standard.md`) - Every observable side effect must be asserted completely: database writes (all fields), file writes (full content), events (all payload fields), queue messages (all fields). Returning the correct value while ignoring side effects is a Green Mirage.
- **Green Mirage Pattern 10: "Strengthened Assertion That Is Still Partial"** (`commands/audit-mirage-analyze.md`) - Catches fixes that replace one weak assertion with another (e.g., replacing `assert len(x) > 0` with `assert "keyword" in result`). Both are BANNED. A real fix must reach Level 4+.
- **Phase 3.5: Mandatory Post-Fix Adversarial Review** (`skills/fixing-tests/SKILL.md`) - After all fixes are applied, a Test Adversary subagent verifies every new assertion meets Level 4+ and checks for Pattern 10 violations. Previously, adversarial review was only available through the green mirage audit's end-to-end flow.
- **Inline assertion quality requirements in fix-tests-execute** (`commands/fix-tests-execute.md`) - The fix execution prompt now embeds the Full Assertion Principle, BANNED patterns list (including mock.ANY and incomplete mock calls), and per-assertion verification requirements directly. Previously relied on orchestrator to append the Test Writer Template, which was not enforced.
- **Anti-Pattern 7: Partial-to-Partial Upgrades** (`skills/test-driven-development/testing-anti-patterns.md`) - New testing anti-pattern covering fixes that move from one BANNED assertion level to another without reaching Level 4+.

### Changed
- **Pattern 2 renamed from "CODE SMELL" to "BANNED"** (`commands/audit-mirage-analyze.md`) - Pattern 2 (Partial Assertions) changed from "CODE SMELL - INVESTIGATE DEEPER" to "Partial Assertion on Any Output (BANNED)". Language changed from investigative to prohibitive. Applies to all output regardless of determinism.
- **Phase 7 Fix Verification made MANDATORY** (`skills/auditing-green-mirage/SKILL.md`) - Was conditional on "end-to-end" usage; now required whenever fixes are written through any path. New Step 0 (Full Assertion Check) runs before all other analysis, covering all output types and mock call assertions.
- **Assertion Quality Gate expanded to ALL modes** (`skills/fixing-tests/SKILL.md`) - Was only enforced in `audit_report` mode; now applies to `general_instructions` and `run_and_fix` modes too.
- **Subagent dispatch prompts require explicit Read() directives** - All test-related subagent prompts across `auditing-green-mirage`, `fixing-tests`, `dispatching-parallel-agents`, and `feature-implement` now include explicit "Read these files in full" instructions and anti-shortcut mandates. Changed "Load" to "Read" throughout.
- **Test Writer Template strengthened** (`skills/dispatching-parallel-agents/SKILL.md`) - Full Assertion Principle as Rule 0 (all output, not just deterministic), mock call assertion requirements as Rule 6, additional BANNED patterns (multiple partials, tautological assertions, mock.ANY), no partial-to-partial upgrade mandate.
- **Test Adversary Template strengthened** (`skills/dispatching-parallel-agents/SKILL.md`) - Added immediate rejection criteria, Full Assertion Principle in verdicts, Pattern 10 detection in summary, mock.ANY as immediate rejection.
- **TDD skill assertion rules table** (`skills/test-driven-development/SKILL.md`) - Renamed columns to "BANNED Pattern / CORRECT Pattern" with explicit Level labels. Added rows for multiple partials, tautological assertions, mock.ANY, and incomplete mock call assertions. New CRITICAL section for Full Assertion Principle.
- **Code quality checklists** (`skills/enforcing-code-quality/SKILL.md`) - Added Full Assertion Principle enforcement, mock.ANY ban, every-mock-call-with-all-args requirement, Pattern 10 awareness, and tautological assertion ban.
- **Green mirage pattern count** - Updated all references from "9 Green Mirage Patterns" to "10 Green Mirage Patterns" and "patterns 1-8" to "patterns 1-10" across skills and commands.
- **Effort estimation tables** - "Strengthen partial assertions" replaced with "replace partial assertions with exact equality (Level 4+)" in audit skill and command.
- **Code review anti-patterns** (`patterns/code-review-antipatterns.md`) - Green Mirage detection heuristics updated with BANNED substring pattern (all output, not just deterministic), Pattern 10 reference, Full Assertion Principle cross-reference, mock.ANY ban, and incomplete mock call assertion ban.

## [0.17.0] - 2026-03-01

### Added
- **Assertion quality standard pattern** (`patterns/assertion-quality-standard.md`) - Shared reference document defining the Assertion Strength Ladder (5 levels for string, object, and collection output), the Bare Substring Problem, the Broken Implementation Test (mutation check annotation), and justification requirements. Referenced by TDD, green mirage audit, fixing-tests, and code quality skills.
- **Fix verification phase for green mirage audit** - Phase 7 in `auditing-green-mirage` closes the audit-to-fix loop with a Test Adversary subagent that applies ESCAPE analysis and assertion ladder classification to every new assertion
- **Specialized subagent templates** (`dispatching-parallel-agents`) - Test Writer and Test Adversary templates for consistent assertion quality enforcement when dispatching test-writing or test-reviewing subagents
- **Assertion quality gate for fixing-tests** - `audit_report` mode loads the assertion quality standard and rejects assertions below Level 4 on the Assertion Strength Ladder

### Changed
- **TDD skill assertion rules expanded** - Added bare substring ban, string containment position requirement, and MUTATION field to ESCAPE analysis template
- **Code quality checklists updated** - Both pre-completion and post-implementation checklists now require Level 4+ assertions per the Assertion Strength Ladder

## [0.16.0] - 2026-03-01

### Added
- **Assertion quality enforcement across skill system** - Defense-in-depth approach to prevent green mirage tests (tests that pass but don't validate correctness)
  - **TDD skill**: Mandatory ESCAPE analysis per test function (5-field template: CLAIM/PATH/CHECK/ESCAPE/IMPACT), assertion quality rules banning `len() > 0`, `len() == N`, `mock.ANY`, and existence-only checks without content verification. 4 new self-check items enforce compliance.
  - **Testing anti-patterns**: New Anti-Pattern 6 (Existence-Only Assertions) with violation examples, fix examples, pychoir exception rule, and gate function. Cross-references Green Mirage Pattern 1.
  - **Green mirage audit**: Worked ESCAPE example showing good vs bad analysis of a weak test. Pattern 1 expanded to detect count-only (`len() == N`) and wildcard matcher (`mock.ANY`, `unittest.mock.ANY`) assertions. Pattern 2 expanded with pychoir/matcher investigation point.
  - **Implementing-features**: SIMPLE tier no longer exempts green mirage audit. All tiers now run the audit when tests are written or updated. Fact-checking exemption remains for SIMPLE tier.

### Fixed
- **Green mirage pattern count** - Fixed stale reference "8 Green Mirage Patterns" to "9 Green Mirage Patterns" in auditing-green-mirage skill

## [0.15.2] - 2026-03-01

### Fixed
- **TTS plays to stale audio device** - Changing the system default output device after the MCP daemon started had no effect; playback always targeted the device that was default at startup. PortAudio now re-initializes before each playback to pick up the current system default (`spellbook/tts.py`)

## [0.15.1] - 2026-03-01

### Changed
- **Bump dependencies** - fastapi 0.128.0 -> 0.134.0, @types/node 20.19.30 -> 25.3.3, @opencode-ai/plugin 1.2.14 -> 1.2.15, @opencode-ai/sdk 1.2.14 -> 1.2.15, actions/upload-artifact v6 -> v7

## [0.15.0] - 2026-02-28

### Added
- **Compiled Nim hooks with shell fallbacks** - All 9 Claude Code hooks now have native Nim implementations that launch in ~5ms instead of ~200ms for Python/shell scripts. Includes a codegen pipeline (`hooks/nim/generate_patterns.py`) that reads security rules from Python and generates a Nim module with pre-compiled regex patterns and SHA1 hash verification. If Nim is not installed or any hook fails to compile, all hooks fall back to shell scripts (all-or-none strategy).
  - **9 Nim hook binaries**: `tts_timer_start`, `bash_gate`, `spawn_guard`, `state_sanitize`, `audit_log`, `canary_check`, `tts_notify`, `pre_compact_save`, `post_compact_recover`
  - **Shared hooklib module** (`hooks/nim/src/hooklib.nim`): JSON stdin parsing, recursive string extraction, MCP JSON-RPC client with SSE response parsing, fail-open/fail-closed exit handlers, SHA1 hash verification
  - **Security pattern sync**: Generated patterns include SHA1 hash of source rules; at runtime, hooks verify the hash and fall back to MCP `security_check_tool_input` if patterns are stale
  - **Installer integration**: `_detect_nim()` checks for Nim >= 1.6, `_compile_nim_hooks()` builds all binaries, `nim_available` flag propagated through hook registration to select Nim binary or shell fallback per hook
- **`security_check_tool_input` MCP tool** - New tool that validates tool call inputs against security rules, used as runtime fallback when Nim hooks detect stale compiled patterns (`spellbook/server.py`)

### Changed
- **Green mirage audit expanded** - Added detection of skipped, xfailed, or disabled tests hiding real failures (`commands/audit-green-mirage.md`, `commands/audit-mirage-analyze.md`, `commands/audit-mirage-cross.md`, `commands/audit-mirage-report.md`, `skills/auditing-green-mirage/SKILL.md`)
- **Mermaid diagram guidance** - Added rule to use `<br>` for newlines within mermaid node labels instead of literal newlines (`AGENTS.spellbook.md`)

## [0.14.0] - 2026-02-28

### Changed
- **Rename CLAUDE.md to AGENTS.md** - Project development instructions now live in `AGENTS.md` (platform-agnostic naming). `CLAUDE.md` remains as a thin shim pointing to `AGENTS.md`. User-facing template renamed from `CLAUDE.spellbook.md` to `AGENTS.spellbook.md`. Installation targets unchanged (Claude Code still writes to `~/.claude/CLAUDE.md`).
- **Rename `get_spellbook_claude_md_content` to `get_spellbook_context_content`** - Function in `installer/components/context_files.py` renamed to reflect platform-agnostic naming. Backward-compatible alias retained.
- **Shell/PowerShell parity rule** - Added development rule requiring shell script changes to have corresponding PowerShell/Python wrapper changes (`AGENTS.md`).

### Fixed
- **Hook format validation errors on startup** - `bash-gate.sh` and `spawn-guard.sh` were registered as plain string paths instead of the required object format `{"type": "command", "command": "..."}`. Claude Code rejected these on startup with a settings validation error (`installer/components/hooks.py`).
- **Hooks installed to wrong settings file** - Installer wrote hooks to `~/.claude/settings.local.json`, which Claude Code does not read for hooks at the user level. Changed to `~/.claude/settings.json` (`installer/platforms/claude_code.py`).

## [0.13.1] - 2026-02-28

### Fixed
- **IndexError in TTS notification hook** - `shlex.split(cmd)[0]` crashes when the command string is empty or whitespace-only; now guards against empty list before indexing (`hooks/tts-notify.py`, `hooks/tts-notify.sh`)
- **Bare except in TTS notification hook** - Narrowed `except:` to `except ValueError:` so `SystemExit` and `KeyboardInterrupt` propagate correctly (`hooks/tts-notify.sh`)
- **3x file I/O in `tts_config_set`** - Refactored to use new `config_set_many()` for a single atomic read-modify-write cycle instead of three separate `config_set()` calls (`spellbook/server.py`, `spellbook/config_tools.py`)
- **Import organization in MCP server** - Grouped all stdlib imports together before version detection logic per PEP 8 (`spellbook/server.py`)
- **Nonexistent `@types/node@^25.3.0`** - Pinned to `^22.0.0` across all three OpenCode extension package.json files
- **Nonexistent `python:3.14-slim` Docker image** - Changed to `python:3.13-slim` in test Dockerfile
- **Inconsistent `package-lock.json`** - Regenerated lockfile for `extensions/opencode/context-curator` to resolve nested SDK version mismatch
- **Test tier time boundary inconsistency** - Aligned integration tier to "1-5s" and E2E/Slow to ">5s" to match the `slow` mark definition (`CLAUDE.spellbook.md`)
- **Ambiguous `gpu / hardware` test mark** - Changed to comma-separated `` `gpu`, `hardware` `` to clarify these are two distinct pytest marks (`CLAUDE.spellbook.md`)
- **"All 5 escape strategies" text outdated** - Changed to "escape strategies 1-5" since fractal exploration is now strategy 6 (`commands/deep-research-investigate.md`)
- **`VALID_CHECKPOINT_MODES` undocumented pattern** - Added comment explaining that `depth:N` patterns are also valid but validated separately (`spellbook/fractal/models.py`)
- **Fractal harvest word count ranges unclear** - Labeled each range with its intensity level inline (`commands/fractal-think-harvest.md`)

## [0.13.0] - 2026-02-28

### Changed
- **Fractal-thinking redesign: recursive primitive architecture** - Replaced the 3-phase pipeline (Init/Explore/Synthesize) with a single self-similar recursive primitive and worker-based execution model
  - **New execution model**: Workers pull tasks from a SQL-based work queue with branch affinity and work stealing, instead of round-based cluster dispatch
  - **Bottom-up synthesis**: Each node synthesizes locally from children's results; synthesis cascades upward through the graph rather than being imposed top-down
  - **New MCP tools**: `fractal_claim_work`, `fractal_synthesize_node`, `fractal_get_claimable_work`, `fractal_get_ready_to_synthesize` (17 total fractal tools)
  - **New node statuses**: `claimed` (work in progress) and `synthesized` (local synthesis complete) with schema v1-to-v2 migration
  - **Commands renamed**: `fractal-think-init` -> `fractal-think-seed`, `fractal-think-explore` -> `fractal-think-work`, `fractal-think-synthesize` -> `fractal-think-harvest`
  - **Worker termination**: Workers exit only when no open AND no claimed nodes remain, preventing premature exit race conditions
  - **Budget-exhausted recovery**: Graphs in `budget_exhausted` status can now transition to `active` (for synthesis repair) or `completed`
- **CLAUDE.spellbook.md testing section** - Expanded from single rule to comprehensive test execution strategy: minimum viable test run principle, test tiers table (unit/integration/E2E), change-scoped test selection, batching guidance, writing-tests-for-speed checklist, test marks table, and cross-module regression debugging
- **test-driven-development skill** - Added `Fast` quality row to Good Tests table and new `Test Speed & Scope` section covering resource isolation, input minimization, mark application, and change-scoped test runs
- **fixing-tests skill** - Added `Slow/bloated tests` special case covering mark separation, I/O tier demotion, input shrinking, and fixture weight checks

### Fixed
- **TTS survives daemon venv rebuilds** - When the daemon venv is rebuilt (lockfile hash change), TTS dependencies are now preserved if the user previously opted in
  - `install_daemon()` checks `tts_enabled` config and passes `include_tts=True` to `ensure_daemon_venv()` so TTS deps are included in rebuilds
  - `setup_tts()` detects when TTS was enabled but deps are missing (venv rebuilt) and automatically reinstalls them
  - Fixed misplaced `return` in `setup_tts()` that caused it to silently skip TTS reinstallation
- **spacy model installed during TTS setup** - Kokoro's dependency chain (kokoro -> misaki -> spacy) requires the `en_core_web_sm` language model, which spacy tries to auto-download via `pip install` at runtime. This fails in uv-managed venvs (no pip). The installer now pre-installs the spacy model wheel directly from GitHub Releases via uv during TTS setup.
- **Kokoro model cache detection** - Fixed glob pattern for HuggingFace cache detection (`models--hexgrad--Kokoro*` instead of `models--hexagon*kokoro*`)
- **Kokoro deprecation warning** - Pass explicit `repo_id='hexgrad/Kokoro-82M'` to suppress defaulting warning
- **TTS hook announcements never firing** - Catch-all hooks used `"matcher": ".*"` which Claude Code does not reliably fire. Fixed to omit the `matcher` key entirely (the documented approach for matching all tools). Installer now migrates legacy `".*"`, `"*"`, and `""` matchers on re-install.
- **Daemon venv missing pip causing TTS hangs** - `uv venv` was called without `--seed`, so the daemon venv had no `pip` package. spaCy's runtime pip invocations (spaCy#13747) would hang. Added `--seed` flag to seed pip into the venv at creation time.

### Added
- **Post-compaction context recovery** - Automatically saves and restores orchestrator identity, skill constraints, and workflow state across Claude Code context compactions
  - PreCompact hook (`pre-compact-save.sh`) saves workflow state to MCP daemon before compaction, with fail-open design and 2s timeout budget
  - SessionStart hook (`post-compact-recover.sh`) injects recovery context after compaction via `additionalContext`, with fallback directive when daemon unreachable
  - Enhanced boot prompt with Section 0.6 (orchestrator identity), 0.7 (skill FORBIDDEN/REQUIRED constraints), 0.8 (binding decisions) for post-compaction recovery
  - `get_resume_fields()` now queries `workflow_state` table alongside `souls` for richer resume context
  - `_get_skill_constraints()` extracts FORBIDDEN/REQUIRED sections from SKILL.md files as behavioral guardrails
  - Workflow state validation in `workflow_state_save` (rejects invalid keys) and `workflow_state_load` (warns on invalid keys)
  - Hook registration in installer for both PreCompact and SessionStart phases
  - 59 new tests across hook scripts, resume flow, and boot prompt generation
- **TTS model preloading at daemon startup** - Kokoro model now loads in a background thread when the daemon starts, eliminating the ~100s cold-start delay on first `kokoro_speak` call. Preload is skipped if TTS is disabled or dependencies are unavailable.
- **Daemon install test suite** - 39 tests in `tests/test_daemon_install.py` covering centralized daemon install ordering, platform installer negative tests, `check_daemon_health()`, `get_daemon_python()` symlink preservation, `_get_repairs()` find_spec usage, `ensure_daemon_venv()` hash detection, TTS config inclusion in `install_daemon()`, and `setup_tts()` reinstall behavior

## [0.12.1] - 2026-02-27

### Added
- **Fractal-thinking integration** - Added optional fractal exploration hooks to 14 existing skills, commands, and agents
  - 5 high-value: design-exploration, debugging (3-Fix Rule), devil's advocate, feature-discover, deep-research-investigate
  - 2 medium-high: analyzing-domains, review-design-verify
  - 7 medium: fact-check-verify, write-skill-test, reflexion-analyze, security-auditing, gathering-requirements, crystallize, hierophant-distiller
  - Consistent pattern: trigger condition, intensity level (pulse/explore), seed template, synthesis usage
  - All integrations are optional and non-breaking (markdown instruction changes only)

### Fixed
- **TTS debugging and installer improvements**
  - Fix `kokoro_status` returning misleading `error: null` by calling `_check_availability()` in `get_status()` so actual import errors are reported
  - Fix installer silently skipping TTS when kokoro not installed; now offers to install TTS dependencies interactively
  - Add pip to TTS install flow as workaround for spaCy#13747 (spaCy hangs in uv-managed venvs without pip)
  - Add repairs framework to `session_init` that detects broken TTS config and suggests fix commands
- **MCP server resource cleanup** - Garbage collection and memory reclamation for the long-running MCP daemon
  - SQLite context managers: wrapped all raw `sqlite3.connect()` calls in `try/finally` blocks across health.py, security/tools.py, security/check.py, and server.py to prevent connection leaks on exceptions
  - Bounded compaction tracking: converted `_processed_compactions` from unbounded set to time-expiring dict (1-hour TTL) in SessionWatcher
  - Database pruning: added periodic `_cleanup_stale_data()` to SessionWatcher that prunes old rows from high-volume tables (souls, security_events, skill_outcomes, subagents, decisions, corrections, forge_tokens, tool_analytics, reflections)
  - Graceful shutdown: registered `atexit` hook in server.py to stop watcher threads and close all SQLite connection caches

## [0.12.0] - 2026-02-27

### Added
- **Fractal thinking skill** - Persistent recursive thought engine for deep exploration via 13 MCP tools, SQLite-backed graph storage, and 3 phase commands (`/fractal-think-init`, `/fractal-think-explore`, `/fractal-think-synthesize`)
  - Three intensity levels (pulse/explore/deep) with configurable depth and agent budgets
  - Four checkpoint modes (autonomous, convergence, interactive, depth:N)
  - Convergence and contradiction detection across graph branches
  - Branch saturation tracking with automatic status propagation
  - Separate `fractal.db` with WAL mode and schema versioning
  - Server-side depth budget enforcement and graph status validation
  - 246 tests across 8 test files including end-to-end integration

## [0.11.1] - 2026-02-27

### Added
- **pytest-timeout** - Global 30s timeout prevents any single test from hanging the entire suite
- **pytest-xdist** - Enables parallel test execution with `pytest -n auto`
- **Test marks for targeted running** - `@pytest.mark.integration` (13 files), `@pytest.mark.slow` (2 files), `@pytest.mark.external` (1 file)
- **Subprocess timeouts** - All `subprocess.run()` calls in tests now have explicit `timeout=30`

### Changed
- **Consolidated pytest config** - Deleted `pytest.ini`, moved all config to `pyproject.toml`

## [0.11.0] - 2026-02-27

### Added
- **Kokoro TTS MCP integration** - Text-to-speech via 4 MCP tools (`tts_speak`, `tts_settings`, `tts_set_voice`, `tts_list_voices`), lazy-loaded model, per-session overrides
- **FastMCP v3 compatibility** - Version detection and compat shim for both FastMCP v2 and v3
- **`$SPELLBOOK_DIR` expansion in hooks** - Hook paths now use absolute paths instead of unexpanded variables

### Changed
- **Dependabot rollup** - Bumped 15 dependencies across pip, npm, and GitHub Actions

## [0.10.1] - 2026-02-25

### Added
- **Dependabot configuration** - Automated dependency update PRs for all package ecosystems: pip, GitHub Actions, Go modules, Docker, and npm (tests + OpenCode extensions)
- **Dependabot coverage pre-commit hook** - `check_dependabot_coverage.py` flags any new package manifest (package.json, go.mod, Dockerfile, etc.) not covered by `.github/dependabot.yml`
- **Book-only SVG** - `docs/assets/book.svg` variant of the logo without the star

### Fixed
- **CI test failures on macOS and Linux** - `TestGeminiInstallerIntegration` was calling `install_daemon()` with the real project root, installing an actual launchd/systemd service on CI runners. Mocked `install_daemon` in the test and hardened `test_is_installed_*` tests to use tmp_path-based paths.

## [0.10.0] - 2026-02-24

### Added
- **creating-issues-and-pull-requests skill** - New library skill for template-aware PR and issue creation
  - 4-tier template discovery: local filesystem, GraphQL API, org-level `.github` repo fallback, sensible default
  - Fork-aware: detects cross-repo PRs, uses base repo's templates, confirms target repository
  - YAML issue form support with interactive field walkthrough and `--web` escape hatch
  - Safe `gh` CLI patterns: always `--body-file`, never `--fill`/`--template`/`gh pr edit`
  - Jira-aware PR naming: extracts ticket from branch name, never fabricates
  - Split into orchestrator skill + `/create-pr` and `/create-issue` commands

### Changed
- **All platforms now use HTTP daemon transport** - Removed stdio transport entirely. Gemini CLI, Codex, and Crush now connect to the shared HTTP daemon at `127.0.0.1:8765` (same as Claude Code and OpenCode). Eliminates cold-start latency and fixes Gemini CLI "MCP error -32000: Connection closed" during discovery.
  - `extensions/gemini/gemini-extension.json`: switched from `command`/`args` to `httpUrl`
  - `installer/platforms/gemini.py`: added `install_daemon()` step
  - `installer/platforms/codex.py`: switched TOML config from stdio to HTTP
  - `installer/platforms/crush.py`: switched JSON config from `type: stdio` to `type: http`
  - `spellbook/server.py`: removed stdio-specific UpdateWatcher deferral
  - `spellbook/update_watcher.py`: removed transport parameter (HTTP-only)
- **Docker tests skip by default** - Added `docker` pytest marker; docker tests only run in CI with `--run-docker` flag. Reduces local test suite from ~48min to ~2min.

### Fixed
- **SPELLBOOK_CONFIG_DIR no longer inherits CLAUDE_CONFIG_DIR** - Setting `CLAUDE_CONFIG_DIR` previously caused `SPELLBOOK_CONFIG_DIR` to use the same value as a fallback. These are independent concerns: `CLAUDE_CONFIG_DIR` controls where Claude Code installs its artifacts (skills, commands), while `SPELLBOOK_CONFIG_DIR` controls where spellbook stores its work files. The fallback has been removed from `installer/config.py`, `installer/components/context_files.py`, and `installer/ui.py`.

## [0.9.12] - 2026-02-23

### Added
- **Windows support (beta)** - Cross-platform installation and runtime for Windows
  - `bootstrap.ps1`: PowerShell bootstrap script for Windows installation
  - `installer/compat.py`: Cross-platform abstraction layer (10 functions + 2 classes) for path handling, symlinks, and service management
  - Symlink fallback chain: symlink (Developer Mode) → junction → copy
  - `CrossPlatformLock` with `msvcrt` file locking on Windows, `fcntl` on Unix
  - Service management via Windows Task Scheduler (`schtasks`)
  - Python hook equivalents (`.py`) for all 5 security hooks (bash-gate, spawn-guard, state-sanitize, audit-log, canary-check)
  - `spellbook-watchdog.py`: Windows process watchdog for MCP server lifecycle
  - Windows CI runner in GitHub Actions test matrix (ubuntu, macos, windows)
  - 115 Windows hook tests (83 cross-platform + 32 Windows-only behavioral tests)
  - 71 unit tests for `installer/compat.py`
  - PowerShell bootstrap tests with syntax validation

### Fixed
- **Cross-platform test suite** - Made ~120 tests portable across all 3 OS platforms
  - Path separator assertions use `os.path` instead of hardcoded forward slashes
  - UTF-8 encoding specified for file operations handling Unicode content
  - Platform-aware hook extension assertions (`.sh` vs `.py`)
  - Lock file tests read via held fd instead of reopening (Windows `msvcrt` compat)
  - Resume path regex matches both `/` and `\` separators
- **FastMCP version pinned** to `>=2.0.0,<3` to prevent breaking API changes
- **bootstrap.ps1** checks `$LASTEXITCODE` after `git clone` (PowerShell `$ErrorActionPreference` doesn't catch external command failures)
- **Docker test stability** - Tolerates benign git warnings ("dubious ownership") in `_assert_install_ok()`
- **Concurrent checkpoint test** - Retry logic for file lock contention under thread pressure

## [0.9.11] - 2026-02-19

### Added
- **generating-diagrams skill** - New skill for creating Mermaid and Graphviz DOT workflow diagrams with source-traced nodes
- **Diagram freshness system** - SHA256 hash-based validation for keeping diagrams in sync with source files
  - `check_diagram_freshness.py`: pre-commit hook validates diagram hashes against source content
  - `generate_diagrams.py`: manual generation script using Claude headless invocation
  - Tiered coverage: mandatory for multi-phase skills/commands, optional for simple ones
  - 139 Mermaid workflow diagrams generated (52 skills, 80 commands, 7 agents)
  - Diagrams embedded in doc pages via `generate_docs.py` updates
- **Auto-update system** - Two-phase update architecture for spellbook installations
  - Detection phase: read-only git fetch inside MCP server
  - Application phase: subprocess running installer with git-based rollback
  - Transport-aware scheduling: stdio checks on startup only, HTTP daemons check on startup + configurable interval
  - Major version consent gate, lock file concurrency protection, session greeting notifications
  - New MCP tools: `spellbook_update_check`, `spellbook_update_apply`, `spellbook_update_config`

### Removed
- **Skill registry from CLAUDE.spellbook.md** - Platforms discover skills directly via native mechanisms, making the embedded registry redundant. Simplified `generate_context.py` and `update_context_files.py`.

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
- **24 skill descriptions improved** - Added natural-language trigger phrases, anti-triggers, and disambiguation to skills rated NEEDS_IMPROVEMENT in trigger adequacy audit: test-driven-development, debugging, fixing-tests, code-review, requesting-code-review, writing-plans, design-exploration, devils-advocate, reviewing-design-docs, gathering-requirements, dehallucination, instruction-engineering, using-git-worktrees, merging-worktrees, dispatching-parallel-agents, smart-reading, using-skills, using-lsp-tools, documenting-tools, tarot-mode, distilling-prs, advanced-code-review, auditing-green-mirage, async-await-patterns

### Added
- **Security hardening: defense-in-depth** - Comprehensive security layer for prompt injection, privilege escalation, and data exfiltration protection
  - Runtime input/output checking via `spellbook/security/` module (rules engine, scanner, tools)
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
  - New `spellbook/health.py` module (700+ lines)
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
  - Integrates with design-exploration, writing-skills, and writing-commands skills

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
  - Converted all imports to use full package paths (`from spellbook.x import...`)
  - Removed fragile sys.path manipulation from server.py
  - Added pyproject.toml for proper package installation
  - Updated daemon to run as module (`python -m spellbook.mcp.server`) instead of script
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
  - `tarot-mode` skill: Ten archetypes (Magician, Priestess, Hermit, Fool, Chariot, Justice, Lovers, Hierophant, Emperor, Queen), six with specialized agents
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
  - `spellbook.terminal_utils` - terminal detection and spawning utilities
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

[Unreleased]: https://github.com/axiomantic/spellbook/compare/v0.9.11...HEAD
[0.9.11]: https://github.com/axiomantic/spellbook/compare/v0.9.10...v0.9.11
[0.9.10]: https://github.com/axiomantic/spellbook/compare/v0.9.9...v0.9.10
[0.9.9]: https://github.com/axiomantic/spellbook/compare/v0.9.8...v0.9.9
[0.9.8]: https://github.com/axiomantic/spellbook/compare/v0.9.7...v0.9.8
[0.9.7]: https://github.com/axiomantic/spellbook/compare/v0.9.6...v0.9.7
[0.9.6]: https://github.com/axiomantic/spellbook/compare/v0.9.5...v0.9.6
[0.9.5]: https://github.com/axiomantic/spellbook/compare/v0.9.4...v0.9.5
[0.9.4]: https://github.com/axiomantic/spellbook/compare/v0.9.3...v0.9.4
[0.9.3]: https://github.com/axiomantic/spellbook/compare/v0.9.2...v0.9.3
[0.9.2]: https://github.com/axiomantic/spellbook/compare/v0.9.1...v0.9.2
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
