# permissions-from-transcripts

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when seeding the project's `permissions.allow` list from observed YOLO sessions. Triggers: 'find safe commands to allow', 'review past transcripts for permissions', 'seed the allow list from YOLO sessions', 'propose permissions allow list', 'reduce permission prompts from transcripts'. NOT for: live permission grants during a session (use `/permissions`) or settings.json edits (use update-config).
## Skill Content

``````````markdown
<analysis>
Re-runnable workflow that reads Claude Code JSONL transcripts, classifies recorded Bash commands by safety category, and emits a reviewable proposal for the project's `permissions.allow`. Backed by `spellbook.gates.transcript_analyzer` so the same classification powers this skill and the underlying script.
</analysis>

<reflection>
Did I run with `--dry-run` first, review the rejected/unclassified buckets before writing, and confirm no mutating commands leaked into the proposed allow categories?
</reflection>

# Permissions From Transcripts

**Type:** Workflow + CLI wrapper

Propose a `permissions.allow` array by analyzing successful Bash invocations
recorded in past Claude Code sessions. The skill NEVER writes
`settings.json`. It produces a JSON proposal under
`~/.local/spellbook/state/proposed_allow_list.json` (unless `--dry-run`)
plus a human-readable summary on stdout. The operator reviews the proposal
and decides what to merge into the project's settings.

## Invariant Principles

1. **Never write settings.json** - The skill writes only to the proposal
   path. Promotion into the project's `permissions.allow` is a separate,
   manually approved step. Mutating commands MUST stay in the
   `rejected_mutating` bucket.
2. **Successful invocations only** - A Bash tool_use is considered only
   when paired with a non-error tool_result. Interrupted/unpaired
   invocations are dropped so untested commands cannot seed the allow
   list.
3. **Classification lives in one place** - All classification + bucketing
   logic is in `spellbook.gates.transcript_analyzer`. Do not copy or
   redefine `MUTATING`, `READ_ONLY_SAFE`, etc. inside the skill or the
   script.

## Args

| Arg | Default | Effect |
|-----|---------|--------|
| `--days N` | `30` | Only consider records timestamped within the last N days. |
| `--include-mutating` | `false` | Surface mutating commands in stdout/JSON for visibility. They stay in `rejected_mutating` and are never promoted. |
| `--dry-run` | `true` | Print the summary, skip writing the proposal JSON. Pass `--no-dry-run` (i.e. omit `--dry-run` in the CLI; the script defaults to writing) when you want the proposal persisted. |
| `--config-dir PATH` | `~/.claude-work/projects` and `~/.claude/projects` | Repeatable. Root directory to scan. |
| `--output PATH` | `~/.local/spellbook/state/proposed_allow_list.json` | Where the proposal is written when not dry-running. |

The skill's `--dry-run` default is `true` to match the safe-by-default
posture: callers must opt in to writing the proposal file. The underlying
script defaults to writing because that is the canonical operator flow;
when invoked through the skill, always pass `--dry-run` first and only
re-run without it after reviewing the output.

## Workflow

1. **Dry-run first.** Invoke the analyzer with `--dry-run` and review the
   stdout summary. Pay attention to:
   - The `rejected_mutating` block - confirm every entry is truly
     mutating. If a read-only command is being rejected, that is a
     classification bug in `transcript_analyzer.py`, not a skill issue.
   - The `unclassified` block - manually decide whether each entry
     belongs in an allow category, the reject list, or stays
     unclassified.
2. **Review and approve.** Compare the proposal against the project's
   current `.claude/settings.json` `permissions.allow`. Decide which
   patterns to add. Mutating entries are NEVER promoted.
3. **Persist (optional).** Re-run without `--dry-run` to write the
   proposal JSON. Use the result as a checklist when editing
   `permissions.allow` manually or via the `update-config` skill.

## Invocation

```bash
# Dry-run preview (default for the skill)
uv run python scripts/analyze_yolo_transcripts.py --days 30 --dry-run

# Persist the proposal for offline review
uv run python scripts/analyze_yolo_transcripts.py --days 30

# Custom transcript root + verbose mutating audit
uv run python scripts/analyze_yolo_transcripts.py \
  --config-dir ~/.claude/projects \
  --include-mutating
```

## Library Reuse

When you need the classifier from inside Python (e.g. a custom report or
test):

```python
from spellbook.gates.transcript_analyzer import (
    bucket_and_classify,
    classify,
    extract_bash_commands,
    render_proposed_list,
)
```

The script in `scripts/analyze_yolo_transcripts.py` is a thin CLI wrapper
over these functions; the skill does not maintain its own copy of the
category tables.

## When NOT to Use

- **Editing `permissions.allow` directly** - use the `update-config`
  skill.
- **Live permission grants during a session** - use the platform's
  `/permissions` command.
- **Auditing skills/commands for security issues** - use
  `security-auditing`.
``````````
