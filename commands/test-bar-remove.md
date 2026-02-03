---
description: "Remove test bar artifacts injected by /test-bar. Use when user says /test-bar-remove or wants to clean up QA overlay code"
---

# MISSION

Cleanly and completely remove all test apparatus code injected by `/test-bar`. Restore every modified file to its pre-injection state. Delete every created file. Verify the working tree is clean relative to the branch's actual feature changes.

<ROLE>
Cleanup Agent. You remove throwaway test code surgically and completely. You leave no trace of the test apparatus behind. You are paranoid about leftover imports, dangling references, and partial reverts.
</ROLE>

## Invariant Principles

1. **Safety before speed** - Check for user modifications before reverting. Never destroy work the developer added on top of the test bar injection.
2. **Manifest is source of truth** - The manifest tells you exactly what was created and modified. Trust it over heuristics.
3. **Verify after removal** - Confirm the project compiles and no broken imports remain. A partial removal is worse than no removal.
4. **Graceful fallback** - If the manifest is missing, attempt heuristic detection. If heuristic detection fails, report clearly and exit.

---

## Step 1: Read Manifest

```bash
cat ~/.local/spellbook/test-bar-manifest.json 2>/dev/null
```

**If manifest exists:** Parse it and proceed to Step 2.

**If manifest does NOT exist:** Fall back to heuristic detection:

```bash
# Search for test bar artifacts
echo "=== COMPONENT FILES ==="
find src/ -name "TestScenarioBar*" -o -name "testScenarioData*" 2>/dev/null

echo "=== INJECTION POINTS ==="
grep -rn "TestScenarioBar\|test-scenario-bar\|Test Scenario Bar" src/ \
  --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" 2>/dev/null

echo "=== DEV-ONLY COMMENTS ==="
grep -rn "DEV-ONLY: Test scenario bar\|remove with /test-bar-remove" src/ \
  --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" 2>/dev/null
```

- If artifacts found: Build a synthetic manifest from the search results and proceed with user confirmation.
- If nothing found: Report "No test bar found to remove. No manifest at ~/.local/spellbook/test-bar-manifest.json and no TestScenarioBar artifacts detected in source." and exit.

---

## Step 2: Safety Check

<CRITICAL>
Before reverting ANY file, check if the developer has made additional changes to files that were modified by `/test-bar`. Blindly reverting would destroy their work.
</CRITICAL>

For each file in `files_modified`:

```bash
# Check if file has changes beyond what /test-bar injected
git diff HEAD -- <file>
```

**If a modified file has ADDITIONAL uncommitted changes beyond the test bar injection:**

Report to the user:

```
WARNING: <file> has been modified since test bar injection.
Reverting will lose these additional changes:

  <show the non-test-bar diff lines>

Options:
  1. Revert anyway (lose additional changes)
  2. Skip this file (manually remove test bar code later)
  3. Stash changes first, then revert (recommended)
```

**If all modified files have ONLY test bar changes:** Proceed to Step 3.

---

## Step 3: Revert Modified Files

For each file in `files_modified`:

```bash
git checkout HEAD -- <file>
```

Verify each checkout succeeded:

```bash
git diff HEAD -- <file>
# Should show no diff (file matches HEAD)
```

If `git checkout` fails (e.g., file was deleted or moved):
- Report the failure with the error message
- Continue with remaining files
- Add failed file to a "manual cleanup needed" list

---

## Step 4: Delete Created Files

For each file in `files_created`:

```bash
# Check if file is tracked by git
if git ls-files --error-unmatch "<file>" 2>/dev/null; then
  # Tracked: restore to HEAD state (removes it if it didn't exist at HEAD)
  git checkout HEAD -- "<file>" 2>/dev/null || rm -f "<file>"
else
  # Untracked: delete directly
  rm -f "<file>"
fi
```

Verify each file was removed:

```bash
ls -la <file> 2>/dev/null && echo "WARNING: File still exists: <file>" || echo "Confirmed removed: <file>"
```

---

## Step 5: Verify Clean State

### 5a: Check for remaining references

```bash
# Search for any remaining test bar artifacts
grep -rn "TestScenarioBar\|testScenarioData\|test-scenario-bar" src/ \
  --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" 2>/dev/null
```

If any references remain:
- Report each one with file path and line number
- These indicate an incomplete removal
- Attempt to clean them (remove import lines, remove JSX references)
- Re-verify after cleanup

### 5b: Compile check

```bash
# Quick type-check to confirm no broken imports
npx tsc --noEmit 2>&1 | grep -i "error" | head -10 || npm run typecheck 2>&1 | grep -i "error" | head -10 || echo "No typecheck command found"
```

If type errors found:
- **Errors referencing removed files** (e.g., "Cannot find module './TestScenarioBar'"): These are dangling imports the revert missed. Fix by removing the offending import/require lines. Re-run type-check.
- **Errors NOT referencing removed files**: These are pre-existing type errors unrelated to test bar removal. Report them in output under "Pre-existing type errors (not caused by removal):" but do NOT attempt to fix them.

### 5c: Git status

```bash
git status --short
```

The output should show no changes related to test bar files. If the branch has other feature changes, those should remain untouched.

---

## Step 6: Delete Manifest

```bash
rm -f ~/.local/spellbook/test-bar-manifest.json
```

Confirm deletion:

```bash
ls ~/.local/spellbook/test-bar-manifest.json 2>/dev/null && echo "WARNING: Manifest still exists" || echo "Manifest removed"
```

---

## Output

After completion, display:

```
Test Bar Removed

Files restored:
  - <path> (reverted to HEAD)
  - <path> (reverted to HEAD)

Files deleted:
  - <path> (removed)
  - <path> (removed)

Remaining references: [none | list of any leftover references]
Type errors: [none | list of any remaining errors]
Manifest: deleted

Working tree status: <clean relative to branch | details if not clean>
```

If any issues remain:

```
Manual Cleanup Needed:
  - <file>:<line> - <description of remaining artifact>
```

---

<FORBIDDEN>
- Reverting files without checking for user modifications first
- Running `git checkout .` or `git clean -fd` on the entire repo (only operate on manifest-listed files)
- Deleting files not listed in the manifest without explicit user confirmation
- Reporting "clean" without verifying no dangling imports remain
- Skipping the compile check
- Proceeding silently when a file revert fails
</FORBIDDEN>

<analysis>
The removal command must be paranoid about two failure modes: (1) destroying developer work by blindly reverting files they modified after injection, and (2) leaving broken imports by incompletely removing references. The safety check in Step 2 and the reference scan in Step 5a address these respectively.
</analysis>

<reflection>
Before reporting completion, verify:
- Did I check every modified file for additional developer changes before reverting?
- Did I confirm every created file was actually deleted?
- Did I scan for remaining TestScenarioBar references after removal?
- Does the project still compile without broken imports?
- Is the manifest file deleted?
- Did I avoid touching any files NOT in the manifest?
</reflection>
