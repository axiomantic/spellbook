# Move Project

Rename a project directory and update all Claude Code session references so session history is preserved.

## Usage
```
/move-project <original> <dest>
```

## Arguments
- `original`: Absolute path to the original project directory (e.g., `/Users/me/Development/old-name`)
- `dest`: Absolute path to the new location (e.g., `/Users/me/Development/new-name`)

## Step 1: Safety Check - Verify Current Directory

**This MUST be the first step before anything else.**

**CRITICAL:** Detect if the current working directory is the original or destination.

```bash
pwd
```

If `pwd` output:
- Equals `<original>` or `<dest>`, OR
- Starts with `<original>/` or `<dest>/` (is a subdirectory)

Then:
1. **STOP IMMEDIATELY**
2. Inform the user:
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

Parse arguments from the command. Both paths must be absolute (start with `/`).

If paths are not provided or invalid, use AskUserQuestion to prompt for them.

## Step 3: Verify Original Exists

```bash
[ -d "<original>" ] && echo "EXISTS" || echo "NOT_FOUND"
```

If NOT_FOUND:
- Show error: "Original directory does not exist: <original>"
- Exit

## Step 4: Verify Destination Does Not Exist

```bash
[ -e "<dest>" ] && echo "EXISTS" || echo "AVAILABLE"
```

If EXISTS:
- Show error: "Destination already exists: <dest>"
- Exit

## Step 5: Find Claude References

### Path encoding

Claude Code encodes paths by replacing `/` with `-`. For example:
- `/Users/me/Development/myproject` → `-Users-me-Development-myproject`

Calculate encoded paths:
```bash
ORIGINAL_ENCODED=$(echo "<original>" | sed 's|/|-|g')
DEST_ENCODED=$(echo "<dest>" | sed 's|/|-|g')
```

### Check for Claude session data

```bash
# Check if projects directory exists
ls -d ~/.claude/projects/"$ORIGINAL_ENCODED" 2>/dev/null

# Count history.jsonl entries
grep -c '"project":"<original>"' ~/.claude/history.jsonl 2>/dev/null || echo "0"

# Also check with escaped slashes (JSON format)
ORIGINAL_ESCAPED=$(echo "<original>" | sed 's|/|\\/|g')
grep -c "\"project\":\"$ORIGINAL_ESCAPED\"" ~/.claude/history.jsonl 2>/dev/null || echo "0"
```

### Show preview

```
Found Claude Code references to update:

~/.claude/projects/<original-encoded>/
  - Contains <count> session files

~/.claude/history.jsonl
  - <count> entries referencing <original>

Filesystem:
  - <original> → <dest>
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

If "Show detailed preview":
- List all files in projects directory
- Show first 5 matching history.jsonl lines
- Ask again

## Step 7: Perform the Move

Execute in this exact order to minimize risk:

### 7a. Update history.jsonl

```bash
# Backup first
cp ~/.claude/history.jsonl ~/.claude/history.jsonl.backup

# Update project paths (handle JSON escaping)
sed -i '' 's|"project":"<original>"|"project":"<dest>"|g' ~/.claude/history.jsonl
```

### 7b. Rename projects directory

```bash
# Only if the encoded directory exists
if [ -d ~/.claude/projects/"$ORIGINAL_ENCODED" ]; then
  mv ~/.claude/projects/"$ORIGINAL_ENCODED" ~/.claude/projects/"$DEST_ENCODED"
fi
```

### 7c. Rename filesystem directory

```bash
mv "<original>" "<dest>"
```

## Step 8: Verify and Report

```bash
# Verify new location exists
[ -d "<dest>" ] && echo "FS_OK" || echo "FS_FAIL"

# Verify projects directory renamed
[ -d ~/.claude/projects/"$DEST_ENCODED" ] && echo "PROJECTS_OK" || echo "PROJECTS_SKIP"

# Verify history.jsonl updated
grep -c '"project":"<dest>"' ~/.claude/history.jsonl
```

### Success report

```
Project moved successfully.

Filesystem:
  <original> → <dest>

Claude Code:
  ~/.claude/projects/<dest-encoded>/ (renamed)
  ~/.claude/history.jsonl (<count> entries updated)

Backup created at: ~/.claude/history.jsonl.backup

To use the project in its new location:
  cd <dest> && claude
```

## Error Handling

If any step fails:
1. Show the specific error
2. Attempt rollback if possible:
   - If history.jsonl was backed up, restore it
   - If projects directory was moved but filesystem move failed, move it back
3. Report what was and wasn't changed

## Edge Cases

### No Claude session data exists
If no projects directory or history entries exist for the original path:
- Warn user: "No Claude Code session data found for <original>"
- Ask if they want to proceed with just the filesystem rename
- If yes, just do `mv <original> <dest>`

### Parent directory doesn't exist for destination
```bash
mkdir -p "$(dirname "<dest>")"
```
Create parent directories as needed before the move.
