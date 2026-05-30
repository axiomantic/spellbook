---
name: rounding-up-worktree-sessions
description: "Use when scattered Claude Code sessions need to be found, grouped by effort, relocated to the right worktree's resume picker, or reopened together. Triggers: 'round up my sessions', 'find my worktree sessions', 'reopen my claude sessions by worktree', 'reorient sessions', 'relaunch sessions', 'resume my recent sessions grouped by worktree', 'my sessions are scattered', 'open all sessions for this effort'. NOT for: relocating a project's sessions because the CODE moved (use move-project); creating worktrees (use using-git-worktrees)."
---

# Rounding Up Worktree Sessions

<ROLE>
Session Wrangler. You orchestrate `roundup.py` and conduct the human confirmation gates. You never compute encodings, groupings, or move plans yourself — the helper is deterministic and unit-tested; you delegate all logic to it and own only the interaction.
</ROLE>

**Announce:** "Using rounding-up-worktree-sessions skill."

## Overview

A single multi-repo effort spawns several Claude Code sessions across several worktrees and sometimes two config stores (`~/.claude`, `~/.claude-work`). Sessions get started in the wrong cwd, pick up `-a/-b/-c` title disambiguators, and scatter under `$CONFIG/projects/<encoded-cwd>/`. This skill finds recent sessions, groups them by the effort they belong to, optionally **reorients** their metadata to the correct worktree location, and optionally **relaunches** them as Ghostty windows/panes.

You are the orchestrator. `roundup.py` (sibling file, stdlib-only) does the work. You call its subcommands and conduct three AskUserQuestion gates.

<analysis>
Before acting, establish: which config dirs are in scope (`~/.claude` always; `~/.claude-work` only if the user opts in), the lookback window, and whether the user's intent is inspection only, reorientation, relaunching, or all three. The plan JSON the helper emits is the single source of truth for groupings, resolved worktrees, confidence, and reorient candidates — read it, do not infer.
</analysis>

## Invariant Principles

1. **The helper owns all logic.** Encodings, worktree derivation, grouping, move-plan computation, and AppleScript generation are computed ONLY by `roundup.py`. You never reconstruct them in your head or in shell — you call subcommands and read their JSON.
2. **Preview before mutation.** Every reorientation is shown via `reorient --dry-run` and confirmed by the user before any file moves. `--update-history` stays OFF unless the user explicitly opts in.
3. **Metadata only, never code.** Reorientation moves only Claude session files within one config dir. It never touches worktrees, git state, or source, and never crosses config stores.
4. **Per-item reorient, global open.** Reorientation is confirmed one session at a time (two sessions in a group may target different worktrees). Opening is a single global yes/no that launches every group.
5. **Opening is decoupled from reorientation.** A launch works whether or not a session was reoriented, because each pane `cd`s to the session's real storage cwd.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| config dirs | Yes | Which Claude config stores to scan (`~/.claude` default; `~/.claude-work` optional). |
| lookback window | Yes | How far back to consider sessions (ISO date → `--since`, or hours/days → `--lookback-hours`). |
| reorient decisions | Per-item | For each candidate: reorient to project subdir, to workspace root, or skip. |
| open decision | Global | Whether to relaunch all groups in Ghostty. |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| grouping preview | Display | Per-group session list with resolved worktree, confidence, and current location. |
| reoriented sessions | Side effect | Session metadata moved to the correct project dir (after dry-run + confirm). |
| Ghostty windows | Side effect | One window per group, one split pane per session, each resuming its session. |

## When to Use

- User wants to see every session belonging to one effort in one place.
- Sessions don't appear in the right interactive resume picker because their stored project dir doesn't match the worktree they were really worked in.
- User wants to bring a whole effort's sessions back up at once.
- **NOT** when code physically moved (that's `move-project`). **NOT** to create worktrees (that's `using-git-worktrees`).

## Terminology

| Term | Meaning |
|------|---------|
| **reorient** | Move ONLY a session's Claude metadata files (`<uuid>.jsonl` + sibling `<uuid>/` sidecar) within the SAME config dir, into the project dir of its correct worktree. It does **NOT** move code, never touches git/worktrees, and never crosses config dirs. Contrast `move-project`, which relocates sessions because the underlying code moved. |
| **group** | The set of sessions belonging to one effort (keyed by title prefix, corroborated by worktree). One Ghostty window per group. |
| **config dir** | A Claude Code config store root (`~/.claude` default, optionally `~/.claude-work`). |

## The Flow (exact sequence)

You run these gates in order. Do not skip the dry-run preview, and do not flip `--update-history` on without explicit opt-in.

### ASK #1 — config dirs + lookback window

Use AskUserQuestion.

**Config dirs (multi-select):**
- `~/.claude` (default, pre-selected)
- `~/.claude-work`

Pass each chosen dir as a repeated `--config-dir` flag.

**Lookback window:**
- `24h`
- `3 days` (72h, default)
- `7 days`
- `Custom` (free-form)

Parse a free-form custom answer into EXACTLY ONE flag (they are mutually exclusive):
- An **ISO-8601 date/datetime** (`2026-05-20`, `2026-05-20T09:00:00Z`) → `--since <ISO>`.
- A **duration** (`48`, `48h`, `7d` → 168) → `--lookback-hours N`.

### Step 2 — build the plan

```bash
python3 roundup.py plan --json \
  --config-dir ~/.claude [--config-dir ~/.claude-work] \
  ( --lookback-hours N | --since ISO )
```

Parse the JSON plan envelope: `sessions` (each enriched with `resolved_worktree_dir`, `resolved_workspace`, `workspace_root_dir`, `resolve_confidence`, `resolve_signal`, `appears_running`, `encoded_cwd_current`), `groups`, `reorient_candidates`, `warnings`. Save the plan to a temp file — `reorient` and `launch` consume it.

### Step 3 — present the grouping (dry-run-style preview)

One section per group. For each session show: `uuid`, `title`, resolved worktree + `resolve_confidence`, and its current location (`encoded_cwd_current`). Surface every plan `warning`.

```
Group: ody-2957-styleseat  (3 sessions)
  uuid    title                 resolved worktree                conf   running
  0f3c..  ody-2957-styleseat-a  worktrees/ODY-2957.../styleseat   high   no
  9ab1..  ody-2957-styleseat-b  worktrees/ODY-2957.../mobileweb   high   no
  7b2c..  ody-2957-styleseat-c  (UNRESOLVED — gitBranch=HEAD)     -      no
```

### ASK #2 — reorientation, PER ITEM

For EACH uuid in `reorient_candidates`, ask an individual decision (one AskUserQuestion per candidate, or a multiSelect that still records one target per candidate). Sessions that are UNRESOLVED, already-correct, or running are NOT in `reorient_candidates` — do not offer them.

For each candidate, show its current project dir and offer:
- **Repo subdir** → `<resolved_worktree_dir>` (suggested default)
- **Workspace root** → `<workspace_root_dir>` — offer this option ONLY when the plan marks `workspace_root_dir` non-null (main repos have none; suppress it for them)
- **Skip**

Collect decisions into a JSON array:

```json
[{"uuid": "0f3c...", "config_dir": "/Users/eek/.claude", "target": "repo_subdir"},
 {"uuid": "9ab1...", "config_dir": "/Users/eek/.claude", "target": "workspace_root"},
 {"uuid": "7b2c...", "config_dir": "/Users/eek/.claude", "target": "skip"}]
```

**Dry-run FIRST, then live.** Always preview before mutating:

```bash
python3 roundup.py reorient --plan <plan.json> --decisions <decisions.json> --dry-run --json
```

Show the exact planned moves (old project dir → new project dir, per item). Only after the user confirms the preview, run it for real. **Always pass `--summary-out <reorient-summary.json>`** so the launch step (ASK #3) can cd reoriented sessions to their NEW dir without a re-scan:

```bash
python3 roundup.py reorient --plan <plan.json> --decisions <decisions.json> \
  --summary-out <reorient-summary.json> --json
```

Remember the `<reorient-summary.json>` path; ASK #3 needs it. `--update-history` stays OFF unless the user explicitly opts in. Note when offering it: the history rewrite is best-effort and backs up `history.jsonl` to a timestamped `.backup.<stamp>` first. Surface every `skipped` / `collisions` / `rolled_back` / `warnings` entry verbatim.

### ASK #3 — open everything (single global yes/no)

> Open all groups now? This launches one Ghostty window per group, one pane per session, each resuming its session with the launcher's standard resume command (`claude … --resume <uuid>`, with the skip-permissions flag the helper already supplies).

On **Yes**:

- **If a live reorient ran THIS run** (ASK #2 executed for real, producing `<reorient-summary.json>`), pass it so sessions reoriented this run cd to their NEW dir:

  ```bash
  python3 roundup.py launch --plan <plan.json> --reorient-summary <reorient-summary.json> --json
  ```

- **If NO reorient ran this run** (or only a dry-run), omit the flag:

  ```bash
  python3 roundup.py launch --plan <plan.json> --json
  ```

This opens one Ghostty window per group (panes = sessions). Each pane runs a command of the form (the skip-permissions flag, spelled `--dangerously` + `-skip-permissions`, is supplied by `roundup.py` — see `build_pane_command`):

```
cd <dir> && CLAUDE_CONFIG_DIR=<cfg> claude <skip-perms-flag> --resume <uuid>
```

Tell the user: the **first** launch triggers a one-time macOS Automation (TCC) permission prompt ("control Ghostty"); approve it once and subsequent runs are silent. Surface every per-session launch WARNING the helper emits (some sessions may not auto-resume).

## Safety Invariants

- **Reorient previews before it mutates.** Always run `--dry-run` and get confirmation first.
- **Never overwrites.** A destination collision refuses that item with a warning.
- **Skips running sessions.** Re-checked live at move time (TOCTOU), not just at plan time.
- **`--update-history` default OFF.** Only enabled on explicit opt-in; best-effort with timestamped backup.
- **Same config dir only.** Reorient never crosses `~/.claude` ↔ `~/.claude-work`.
- **Code is never touched.** Reorient moves session metadata files only.

## Known Limitations

- **Resume needs the origin cwd to still exist.** If the resolved/launch dir was deleted, `claude --resume` will fail until it is restored. The launch step warns per affected session.
- **Ghostty native AppleScript backend only** (Ghostty **>= 1.2.0**; verified against the 1.3.1 scripting dictionary). The launch step drives Ghostty's native AppleScript verbs (`make new window`, `split … direction …`, `input text … to <terminal>`, `send key "enter" to <terminal>`). The **first** launch triggers a one-time macOS **Automation** (Apple Events) permission prompt — **not** Accessibility — and there is **no** dependency on any Ghostty keybind. The native AppleScript API has been stable since 1.2.0; it is still a relatively new API and could change in a future major. The `gui` and iTerm2 backends remain **deferred**; `launch` exits non-zero for any non-native / non-Ghostty combination.
- **`~/.claude-work` sessions** resume correctly only because each pane command sets `CLAUDE_CONFIG_DIR` explicitly. Cross-config moves are forbidden, so a `~/.claude-work` session is warned about (not relocated) if its config dir is non-default.

## CLI Reference

Subcommands: `scan`, `plan`, `reorient`, `launch`. Full details in `roundup.py` docstrings.

| Subcommand | Purpose | Key flags |
|------------|---------|-----------|
| `scan` | Discover sessions within the lookback window | `--config-dir` (repeatable), `--since` / `--lookback-hours`, `--json`, `--out` |
| `plan` | Derive worktrees + group; emit the plan envelope you drive prompts from | `--config-dir`, `--in`, `--since` / `--lookback-hours`, `--json`, `--out` |
| `reorient` | Preview or execute per-item moves | `--plan`, `--decisions`, `--dry-run`, `--update-history` (default OFF), `--summary-out`, `--json` |
| `launch` | Render + run the Ghostty AppleScript | `--plan`, `--reorient-summary`, `--print-script`, `--json` |

- `--since ISO` and `--lookback-hours N` are mutually exclusive; pass exactly one.
- `--print-script` on `launch` dumps the AppleScript without invoking `osascript` (debugging).

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Computing encodings or groupings yourself | Delegate everything to `roundup.py`; it is deterministic and tested. |
| Running live `reorient` without the dry-run | Always preview first and get confirmation. |
| Offering reorientation for UNRESOLVED / running / already-correct sessions | Only iterate `reorient_candidates`; the helper has already filtered. |
| Offering the workspace-root target for a main repo | Offer it ONLY when `workspace_root_dir` is non-null. |
| Enabling `--update-history` by default | Default OFF; explicit opt-in only. |
| Treating "reorient" like `move-project` | Reorient moves metadata only; `move-project` is for moved code. |

<FORBIDDEN>
- Mutating before showing the `--dry-run` preview and getting confirmation
- Enabling `--update-history` without explicit user opt-in
- Moving sessions across config dirs
- Offering reorientation for sessions not in `reorient_candidates`
- Suppressing or paraphrasing launch warnings (resume may silently fail)
- Computing move plans / encodings / groupings in your own context instead of via `roundup.py`
</FORBIDDEN>

<reflection>
Before declaring done, verify: every reorientation the user approved was previewed and then executed (check the summary for `moved` vs `skipped`/`collisions`/`rolled_back`); any launch warnings were surfaced verbatim; and `--update-history` was only used if the user opted in. If a session failed to resume, confirm its origin cwd still exists on disk and its config dir was passed correctly — do not report success for a pane that errored.
</reflection>
