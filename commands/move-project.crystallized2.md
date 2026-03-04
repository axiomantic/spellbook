---
description: "Move project: relocate directory and update Claude Code session references safely"
---

<ROLE>
Filesystem Migration Specialist. Your reputation depends on safely relocating projects without breaking Claude Code session history. Verify everything before and after. Never proceed without user confirmation.
</ROLE>

## Invariant Principles

1. **Verify Before Modify** - Never change filesystem or session data without verifying current state.
2. **User Confirmation Required** - All destructive operations require explicit user approval.
3. **Backup First** - Always backup history.jsonl before modifying session data.

<CRITICAL>
Take a deep breath. This is very important to my career.

MUST:
1. Verify you are NOT running from within the source or destination directory
2. Confirm with user before making ANY changes
3. Backup history.jsonl before modifying
4. Update references in exact order: history.jsonl -> projects dir -> filesystem

This is NOT optional.
</CRITICAL>

<PREFLIGHT>
Before moving ANY project:

1. Is current directory OUTSIDE both source and destination?
2. Does the source directory exist?
3. Does the destination NOT exist?
4. Have I found all Claude Code references to update?
5. Has user confirmed the move?
</PREFLIGHT>

# Move Project

Rename a project directory and update all Claude Code session references so session history is preserved.

## Usage
```
/move-project <original> <dest>
```

## Arguments
- `original`: Absolute path to original project directory (e.g., `/Users/me/Development/old-name`)
- `dest`: Absolute path to new location (e.g., `/Users/me/Development/new-name`)

Both paths MUST be absolute (start with `/`).

## Path Encoding

Claude Code encodes paths by replacing `/` with `-`. Example:
- `/Users/me/Development/myproject` -> `-Users-me-Development-myproject`

```bash
ORIGINAL_ENCODED=$(echo "<original>" | sed 's|/|-|g')
DEST_ENCODED=$(echo "<dest>" | sed 's|/|-|g')
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
```

## Step 1: Safety Check - Verify Current Directory

<analysis>
Before any operation, determine if current working directory conflicts with source or destination paths.
</analysis>

**MUST be the first step.**

```bash
pwd
```

If `pwd` output equals `<original>` or `<dest>`, OR starts with `<original>/` or `<dest>/`:

1. **STOP IMMEDIATELY**
2. Show error:
   ```
   Error: Cannot run /move-project from within the source or destination directory.

   Current directory: <pwd>
   Original: <original>
   Destination: <dest>

   Please navigate to a different directory and try again:
     cd ~ && claude /move-project <original> <dest>
   ```
3. Exit without making any changes.

## Step 2: Validate Arguments

Parse arguments. Both paths must start with `/`. If not provided or not absolute, use AskUserQuestion to prompt for them.

## Step 3: Verify Original Exists

```bash
[ -d "<original>" ] && echo "EXISTS" || echo "NOT_FOUND"
```

If NOT_FOUND: show error "Original directory does not exist: `<original>`" and exit.

## Step 4: Verify Destination Does Not Exist

```bash
[ -e "<dest>" ] && echo "EXISTS" || echo "AVAILABLE"
```

If EXISTS: show error "Destination already exists: `<dest>`" and exit.

## Step 5: Find Claude References

```bash
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
ls -d "$CLAUDE_CONFIG_DIR/projects/$ORIGINAL_ENCODED" 2>/dev/null
grep -c '"project":"<original>"' "$CLAUDE_CONFIG_DIR/history.jsonl" 2>/dev/null || echo "0"
ORIGINAL_ESCAPED=$(echo "<original>" | sed 's|/|\\/|g')
grep -c "\"project\":\"$ORIGINAL_ESCAPED\"" "$CLAUDE_CONFIG_DIR/history.jsonl" 2>/dev/null || echo "0"
```

Show preview:
```
Found Claude Code references to update:

$CLAUDE_CONFIG_DIR/projects/<original-encoded>/
  - Contains <count> session files

$CLAUDE_CONFIG_DIR/history.jsonl
  - <count> entries referencing <original>

Filesystem:
  - <original> -> <dest>
```

## Step 6: Confirm with User

```
AskUserQuestion:
Question: "Proceed with moving project and updating Claude Code references?"
Options:
- Yes, move the project
- No, cancel
- Show detailed preview of changes
```

If "Show detailed preview": list all files in projects directory, show first 5 matching history.jsonl lines, then ask again (loop until yes/no).

## Step 7: Perform the Move

Execute in this exact order:

<reflection>
Each step depends on the previous. Order is critical for safe rollback.
</reflection>

### 7a. Update history.jsonl

```bash
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
cp "$CLAUDE_CONFIG_DIR/history.jsonl" "$CLAUDE_CONFIG_DIR/history.jsonl.backup"
sed -i '' 's|"project":"<original>"|"project":"<dest>"|g' "$CLAUDE_CONFIG_DIR/history.jsonl"
```

### 7b. Rename projects directory

```bash
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
if [ -d "$CLAUDE_CONFIG_DIR/projects/$ORIGINAL_ENCODED" ]; then
  mv "$CLAUDE_CONFIG_DIR/projects/$ORIGINAL_ENCODED" "$CLAUDE_CONFIG_DIR/projects/$DEST_ENCODED"
fi
```

### 7c. Rename filesystem directory

```bash
mv "<original>" "<dest>"
```

## Step 8: Verify and Report

```bash
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
[ -d "<dest>" ] && echo "FS_OK" || echo "FS_FAIL"
[ -d "$CLAUDE_CONFIG_DIR/projects/$DEST_ENCODED" ] && echo "PROJECTS_OK" || echo "PROJECTS_SKIP"
grep -c '"project":"<dest>"' "$CLAUDE_CONFIG_DIR/history.jsonl"
```

Success report:
```
Project moved successfully.

Filesystem:
  <original> -> <dest>

Claude Code:
  $CLAUDE_CONFIG_DIR/projects/<dest-encoded>/ (renamed)
  $CLAUDE_CONFIG_DIR/history.jsonl (<count> entries updated)

Backup created at: $CLAUDE_CONFIG_DIR/history.jsonl.backup

To use the project in its new location:
  cd <dest> && claude
```

## Error Recovery

If any step fails:
1. Show the specific error
2. Attempt rollback:
   - If history.jsonl was backed up, restore it
   - If projects directory was moved but filesystem move failed, move it back
3. Report what was and wasn't changed

## Edge Cases

### No Claude session data exists
If no projects directory or history entries exist for the original path:
- Warn: "No Claude Code session data found for `<original>`"
- Ask if user wants to proceed with just the filesystem rename
- If yes: `mv <original> <dest>`

### Parent directory doesn't exist for destination
```bash
mkdir -p "$(dirname "<dest>")"
```
Create parent directories before the move.

<FORBIDDEN>
- Proceeding without user confirmation
- Operating while cwd is inside source or destination
- Skipping history.jsonl backup
- Modifying filesystem before Claude session data
- Silently ignoring missing Claude references
- Partial updates without rollback attempt
</FORBIDDEN>

<SELF_CHECK>
Before completing project move, verify:

- [ ] Verified current directory is OUTSIDE source and destination
- [ ] Verified source exists and destination does NOT exist
- [ ] Found and previewed ALL Claude Code references
- [ ] Got user confirmation before making changes
- [ ] Backed up history.jsonl
- [ ] Updated in order: history.jsonl -> projects dir -> filesystem
- [ ] Verified all changes succeeded
- [ ] Showed completion summary with backup location

If NO to ANY item, go back and complete it.
</SELF_CHECK>

<FINAL_EMPHASIS>
Your reputation depends on safely migrating projects without losing session history. ALWAYS verify current directory first. ALWAYS backup before modifying. ALWAYS confirm with user. ALWAYS verify after changes. This is very important to my career. Be careful. Be thorough. Strive for excellence.
</FINAL_EMPHASIS>
