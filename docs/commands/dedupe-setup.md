# /dedupe-setup
## Command Content

``````````markdown
# MISSION

Prepare for instruction deduplication: enforce git safety, then select the
corpus, the seed group, and detection flags.

**Part of the dedupe-* command family.** Run this first, before
`/dedupe-analyze`.

## Invariant Principles

1. **Clean tree required for apply** — the eventual `/dedupe-apply` phase refuses
   to run against a dirty git working tree. Surface this requirement at setup so
   the operator can commit or stash before any edits land.
2. **Corpus is a safe-wide superset** — the corpus is everything the
   external-caller check must not break; it defaults wide (the full instruction
   surface) and may only be narrowed deliberately. When in doubt, scan more.
3. **Group before analysis** — the operator explicitly selects the seed group
   (what may be edited) before any detection runs.
4. **Flags are explicit and bounded** — detection thresholds and the
   `--max-pairs` cost ceiling are chosen up front so classification cost is
   predictable.

<analysis>
Before proceeding, confirm:
- Is the working tree clean? If not, will this run reach apply? If so, the
  operator must commit/stash first.
- Which files form the seed group (what we may edit)?
- Which files form the corpus (the safe-wide superset we must not break)?
- Which thresholds and cost ceiling apply?
</analysis>

## Phase 0: Git Safety

<RULE>Check git state before anything else. The apply phase writes files; the
operator must understand the tree state before reaching it.</RULE>

```bash
git status --porcelain
```

The `/dedupe-apply` phase **refuses to run against a dirty working tree** (design
§8 dirty-tree row). If the output is non-empty, present to the operator:

- **Commit first** — ask for a message, create the commit.
- **Stash first** — stash the changes, proceed.
- **Proceed (analysis/report only)** — detection and reporting are read-only and
  safe on a dirty tree, but apply will refuse until the tree is clean.
- **Abort** — stop.

## Phase 1: Corpus Selection

<RULE>The corpus is the file set the external-caller check (design §5.4) scans.
It defaults wide and is always a superset of the group.</RULE>

- **Default (safe-wide, recommended):** `skills/**/SKILL.md` + `commands/**/*.md`
  + `CLAUDE.md` + `skills/shared-references/*.md` under `$SPELLBOOK_DIR` — the
  full instruction surface. When in doubt, scan MORE files for external callers,
  never fewer.
- **Narrowed:** `--corpus path1,path2,...` — only if the operator deliberately
  scopes down, understanding it narrows the external-caller safety net.

## Phase 2: Seed Group Selection

The seed group is one or more skill/command **names** or **file paths** — what we
may edit. `dedupe.py` transitively expands the seed to its dependents (bounded by
`--max-depth` and the corpus). Ask the operator for the seed group.

## Phase 3: Flag Selection

Choose detection flags (defaults shown):

| Flag | Default | Purpose |
|------|---------|---------|
| `--jaccard-threshold` | 0.7 | Cheap token-overlap gate (Signal 1) |
| `--confirm-threshold` | 0.85 | SequenceMatcher confirm gate (Signal 2) |
| `--external-threshold` | 0.7 | Looser Jaccard gate for external-caller scan |
| `--min-block-chars` | 80 | Below-floor blocks excluded (except fenced-whole) |
| `--max-pairs` | 200 | Cost ceiling: caps classifier dispatches; detect sets `cost_ceiling_exceeded` when confirmed pairs exceed it |
| `--max-depth` | 3 | Bounds transitive group expansion |

The dangerous-action denylist (Clause 3 of INLINE-MANDATORY) is a fixed module constant in this version; a `--danger-denylist` override is a tracked follow-up — see `skills/dedupe/references/verdict-taxonomy.md`.

`--max-pairs` is the true cost backstop (it bounds the expensive classifier
dispatches); raising `--max-depth` cannot, by itself, cause an unbounded batch.

## Output

1. Git state confirmed (clean, committed, stashed, or risk acknowledged).
2. Selected corpus (safe-wide default or narrowed list).
3. Selected seed group.
4. Selected flags.

**Next:** Run `/dedupe-analyze`.

<reflection>
- [ ] Did I check git status and surface the clean-tree-for-apply requirement?
- [ ] Did I default the corpus wide and confirm any narrowing was deliberate?
- [ ] Did the operator select the seed group and flags explicitly?
</reflection>
``````````
