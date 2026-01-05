---
description: Verify all tracks complete, invoke smart-merge, run QA gates, report final integration status.
disable-model-invocation: true
---

# Merge Work Packets

Integrate all completed work packets using smart-merge and verify through comprehensive QA gates.

## Parameters

- `packet_dir` (required): Directory containing manifest.json and completed work packets
- `--continue-merge` (optional): Continue after manual conflict resolution

## Execution Protocol

### Step 1: Load Manifest

```bash
packet_dir="<packet_dir>"
manifest_file="$packet_dir/manifest.json"

# Load manifest using read_json_safe
# Extract:
# - feature name
# - tracks list
# - merge_strategy
# - post_merge_qa gates
# - project_root
```

**Expected manifest fields:**
- `format_version`: "1.0.0"
- `feature`: Feature being integrated
- `tracks`: Array of track metadata
- `merge_strategy`: "smart-merge" or "manual"
- `post_merge_qa`: Array of QA gate commands
- `project_root`: Path to main repository

### Step 2: Verify All Tracks Complete

**Critical gate:** Do NOT proceed unless ALL tracks have completion markers.

```bash
# For each track in manifest
for track in manifest.tracks:
  completion_file="$packet_dir/track-{track.id}.completion.json"

  # Check existence
  if [ ! -f "$completion_file" ]; then
    echo "ERROR: Track {track.id} ({track.name}) incomplete"
    echo "Missing: $completion_file"
    exit 1
  fi

  # Validate completion marker using read_json_safe
  # Verify fields:
  # - format_version: "1.0.0"
  # - status: "complete"
  # - commit: valid git SHA
  # - timestamp: ISO8601 string

  # Check status
  status=$(jq -r '.status' "$completion_file")
  if [ "$status" != "complete" ]; then
    echo "ERROR: Track {track.id} status is '$status', expected 'complete'"
    exit 1
  fi
done

echo "✓ All {track_count} tracks verified complete"
```

**If any track incomplete:**
```
ERROR: Cannot merge - incomplete tracks detected

Incomplete tracks:
  ✗ Track 2: Frontend (no completion marker)
  ✗ Track 4: Documentation (status: in_progress)

Required actions:
1. Complete missing tracks using: /execute-work-packet <packet_path>
2. Verify completion markers exist
3. Re-run merge

Aborting merge.
```

### Step 3: Prepare Branch List for Smart Merge

Extract branch information from manifest:

```bash
# Build list of branches to merge
branches=[]
for track in manifest.tracks:
  branches.append({
    "id": track.id,
    "name": track.name,
    "branch": track.branch,
    "worktree": track.worktree,
    "commit": <commit_from_completion_marker>
  })
done
```

**Display merge plan:**
```
=== Merge Plan ===

Feature: {manifest.feature}
Strategy: {manifest.merge_strategy}
Target: {manifest.project_root}

Branches to merge:
  1. Track 1: Core API
     Branch: feature/track-1
     Commit: abc123
     Worktree: /path/to/wt-track-1

  2. Track 2: Frontend
     Branch: feature/track-2
     Commit: def456
     Worktree: /path/to/wt-track-2

  3. Track 3: Tests
     Branch: feature/track-3
     Commit: ghi789
     Worktree: /path/to/wt-track-3

Total tracks: 3
```

### Step 4: Invoke Smart Merge Skill

**If --continue-merge flag NOT set:**

```
Invoke the smart-merge skill using the Skill tool with:

Context:
- Feature: {manifest.feature}
- Packet directory: {packet_dir}
- Branches: {branches_list}
- Target repository: {manifest.project_root}
- Merge strategy: {manifest.merge_strategy}

Instructions:
1. Analyze all branch diffs since shared setup commit
2. Perform 3-way merge analysis for conflicts
3. Use intelligent conflict resolution strategies
4. Create integration branch with merged code
5. Report conflicts requiring manual resolution

The smart-merge skill will:
- Create merge branch in project_root
- Integrate all track branches
- Detect and resolve conflicts
- Report any manual intervention needed
```

**Smart merge output:**
- Success: All branches merged cleanly
- Partial: Some conflicts auto-resolved, some manual
- Failed: Conflicts require manual resolution

### Step 5: Handle Merge Conflicts

**If smart-merge reports conflicts:**

```
⚠ Merge conflicts detected

Conflicts requiring manual resolution:
  File: src/api/auth.py
    Track 1 changed: authentication logic
    Track 2 changed: API endpoints
    Conflict: Both modified same function signature

  File: frontend/components/Login.tsx
    Track 2 changed: UI component
    Track 3 changed: test fixtures
    Conflict: Import paths differ

Manual resolution required:
1. Navigate to: {manifest.project_root}
2. Review conflicts in merge branch
3. Resolve conflicts manually
4. Commit resolution
5. Re-run: /merge-work-packets {packet_dir} --continue-merge

Options:
  [Manual] - Pause for manual conflict resolution
  [Abort] - Cancel merge, restore pre-merge state

Choose: Manual or Abort?
```

**If user chooses Manual:**
1. Pause execution
2. Display detailed conflict resolution instructions
3. Wait for user to resolve and re-run with --continue-merge

**If user chooses Abort:**
1. Restore pre-merge state
2. Clean up merge branch
3. Exit with error status

### Step 6: Verify Merge Integrity

After merge completes (auto or manual):

```bash
# Navigate to merged branch
cd {manifest.project_root}

# Verify we're on integration branch
current_branch=$(git branch --show-current)
expected_branch="feature/{manifest.feature}-integrated"

if [ "$current_branch" != "$expected_branch" ]; then
  echo "ERROR: Expected branch $expected_branch, on $current_branch"
  exit 1
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
  echo "WARNING: Uncommitted changes detected after merge"
  git status
fi

# Verify all track commits are in history
for track in manifest.tracks:
  commit=$(get_completion_commit(track))
  if ! git merge-base --is-ancestor "$commit" HEAD; then
    echo "ERROR: Track {track.id} commit $commit not in merge history"
    exit 1
  fi
done

echo "✓ Merge integrity verified"
```

### Step 7: Run QA Gates

Execute all gates from `manifest.post_merge_qa`:

```
=== Running QA Gates ===

Gates defined: {manifest.post_merge_qa}
```

**For each QA gate:**

**Gate: pytest**
```bash
# Navigate to project root
cd {manifest.project_root}

# Run pytest with coverage
pytest --verbose --cov --cov-report=term-missing

# Check exit code
if [ $? -eq 0 ]; then
  echo "✓ pytest: PASSED"
else
  echo "✗ pytest: FAILED"
  exit 1
fi
```

**Gate: green-mirage-audit**
```
Invoke the green-mirage-audit skill using the Skill tool

This will:
- Analyze all tests for actual behavior validation
- Detect "green mirage" tests (pass but don't verify)
- Report test quality issues
- Generate audit report

If audit fails:
- Review report in {SPELLBOOK_CONFIG_DIR}/docs/<project>/audits/
- Fix test quality issues
- Re-run merge
```

**Gate: factchecker**
```
Invoke the factchecker skill using the Skill tool with:
- Verify feature requirements met
- Check acceptance criteria from implementation plan
- Validate integration completeness
- Confirm no regressions

If factcheck fails:
- Review discrepancies
- Fix issues in merge branch
- Re-run QA gates
```

**Gate: custom command**
```bash
# For any other command in post_merge_qa
command="<qa_gate_command>"

cd {manifest.project_root}
eval "$command"

if [ $? -eq 0 ]; then
  echo "✓ $command: PASSED"
else
  echo "✗ $command: FAILED"
  exit 1
fi
```

**QA gate summary:**
```
=== QA Gate Results ===

✓ pytest: All tests passed (124/124)
✓ green-mirage-audit: High quality tests, no issues
✓ factchecker: All acceptance criteria met
✓ npm run lint: No linting errors

All gates PASSED
```

### Step 8: Report Final Status

**On success:**
```
✓ Merge completed successfully!

Feature: {manifest.feature}
Integration branch: feature/{feature}-integrated
Tracks merged: {track_count}
QA gates passed: {qa_gate_count}

Summary:
  ✓ All track completion markers verified
  ✓ Smart merge completed without conflicts
  ✓ All QA gates passed
  ✓ Integration branch ready for review

Next steps:
1. Review integration branch:
   cd {manifest.project_root}
   git checkout feature/{feature}-integrated
   git log --graph --all

2. Create pull request:
   gh pr create --title "{feature}" --body "..."

3. After PR approval, merge to main:
   git checkout main
   git merge feature/{feature}-integrated
   git push origin main

4. Clean up worktrees:
   git worktree remove {worktree_paths...}
```

**On failure:**
```
✗ Merge failed

Feature: {manifest.feature}
Failed at: {failure_stage}
Error: {error_message}

Status:
  {completed_steps}
  ✗ {failed_step}: {failure_reason}
  ⏳ {pending_steps}

Resolution:
{specific_instructions_for_failure}

After resolving:
- Re-run: /merge-work-packets {packet_dir} [--continue-merge]
```

## Error Handling

**Incomplete tracks:**
- Detected in Step 2
- List missing completion markers
- Suggest running execute-work-packet for incomplete tracks
- Abort merge

**Merge conflicts:**
- Detected by smart-merge skill
- Display conflict details with file paths and track origins
- Offer Manual resolution or Abort
- If Manual: pause and provide resolution instructions
- If Abort: clean up and exit

**QA gate failures:**
- Stop at first failing gate
- Display gate output and error details
- Do NOT proceed to subsequent gates
- Suggest fixes based on gate type:
  - pytest: fix test failures
  - green-mirage-audit: improve test quality
  - factchecker: address acceptance criteria gaps
  - custom: check command output

**Smart merge skill errors:**
- If smart-merge skill fails to invoke
- If merge strategy unknown
- If worktree paths invalid
- Report error and suggest manual merge

## Recovery

**Continue after manual conflict resolution:**

```bash
# User resolves conflicts manually
cd {manifest.project_root}
# ... resolve conflicts ...
git add .
git commit -m "Resolve merge conflicts"

# Continue merge workflow
/merge-work-packets {packet_dir} --continue-merge
```

With --continue-merge:
- Skip Steps 1-4 (already merged)
- Resume at Step 6: Verify merge integrity
- Run QA gates
- Report final status

## Notes

- All tracks MUST have completion markers before merge
- Smart-merge skill handles complex 3-way merges
- QA gates are mandatory unless manifest overrides
- Integration branch created: feature/{feature}-integrated
- Worktrees remain after merge for inspection
- User manually creates PR after successful merge
- Cleanup of worktrees deferred to user control
- Merge can be re-run with --continue-merge after manual fixes
