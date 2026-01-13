---
description: Verify all tracks complete, invoke worktree-merge, run QA gates, report final integration status.
disable-model-invocation: true
---

# Merge Work Packets

## Invariant Principles

1. **Completeness before integration**: ALL tracks must have valid completion markers before ANY merge begins. Partial integration destroys reproducibility.
2. **Fail fast, fail loud**: Stop at first failure. No cascading errors. Clear diagnosis beats silent corruption.
3. **Evidence over trust**: Every claim (track complete, merge clean, tests pass) requires verifiable proof (file exists, commit in history, exit code 0).
4. **Reversibility**: Pre-merge state must be restorable. Integration branch isolates changes until explicit approval.
5. **Gates are gates**: QA gates are mandatory checkpoints, not suggestions. No gate skipping.

<ROLE>
Integration Lead responsible for final merge quality. Your reputation depends on clean integrations and zero regression escapes.
</ROLE>

## Parameters

- `packet_dir` (required): Directory containing manifest.json and completed work packets
- `--continue-merge`: Resume after manual conflict resolution (skips to integrity verification)

## Reasoning Schema

<analysis>
Before each step: What am I verifying? What evidence proves it?
</analysis>

<reflection>
After each step: Did I get the evidence? What does failure here mean?
</reflection>

## Declarative Workflow

### Phase 1: Manifest and Completion Verification

**Load manifest** from `{packet_dir}/manifest.json`:
- Required fields: `format_version`, `feature`, `tracks`, `merge_strategy`, `post_merge_qa`, `project_root`

**Verify ALL tracks complete**:
- Each track requires `{packet_dir}/track-{id}.completion.json`
- Completion marker must have: `format_version: "1.0.0"`, `status: "complete"`, valid `commit` SHA, ISO8601 `timestamp`
- **Incomplete = ABORT**: List missing tracks, suggest `/execute-work-packet` for each, exit

### Phase 2: Smart Merge Execution

**Display merge plan** before proceeding:
```
Feature: {feature}
Strategy: {merge_strategy}
Target: {project_root}
Branches: [track.id, track.branch, track.commit] for each
```

**Invoke `worktree-merge` skill** with:
- Feature name, packet directory, branch list, target repo, merge strategy

**Handle merge result**:
| Result | Action |
|--------|--------|
| Clean | Proceed to verification |
| Conflicts | Offer Manual (pause + instructions) or Abort (restore + exit) |
| Error | Report, suggest manual merge, exit |

**--continue-merge**: Skip to Phase 3 (assumes conflicts resolved, committed)

### Phase 3: Integrity Verification

**Verify integration branch**:
- Current branch = `feature/{feature}-integrated`
- No uncommitted changes (warn if present)
- All track commits are ancestors of HEAD: `git merge-base --is-ancestor {commit} HEAD`

### Phase 4: QA Gates

**Execute gates from `manifest.post_merge_qa`** (stop at first failure):

| Gate | Invocation |
|------|------------|
| `pytest` | `pytest --verbose --cov --cov-report=term-missing` |
| `audit-green-mirage` | Invoke skill, review report in `{SPELLBOOK_CONFIG_DIR}/docs/<project>/audits/` |
| `fact-checking` | Invoke skill with acceptance criteria from implementation plan |
| Custom | `eval "$command"`, check exit code |

**Gate failure = STOP**: Display output, suggest fixes by gate type, require re-run after fixes.

### Phase 5: Final Report

**Success output**:
```
Feature: {feature}
Integration branch: feature/{feature}-integrated
Tracks merged: {count}
QA gates passed: {count}

Next: Review branch -> Create PR -> Merge to main -> Clean up worktrees
```

**Failure output**: Stage reached, specific error, resolution steps, re-run command.

## Error Recovery Matrix

| Failure Point | Detection | Recovery |
|---------------|-----------|----------|
| Incomplete tracks | Missing/invalid completion markers | Complete tracks, re-run |
| Merge conflicts | worktree-merge reports | Manual resolve, `--continue-merge` |
| QA gate failure | Non-zero exit | Fix issue, re-run from Phase 4 |
| Skill invocation error | Tool failure | Manual merge fallback |

## Constraints

- Integration branch isolates all changes: `feature/{feature}-integrated`
- Worktrees preserved post-merge for inspection
- PR creation is user responsibility (not automated)
- Worktree cleanup deferred to user control

<FORBIDDEN>
- Merging with incomplete tracks (all completion markers required)
- Skipping QA gates or accepting partial gate results
- Deleting worktrees before user confirmation
- Continuing past merge conflicts without explicit resolution
- Modifying track branches during integration
</FORBIDDEN>
