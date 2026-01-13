# /move-project

## Command Content

``````````markdown
# Move Project

Relocate project directory + update all Claude Code session references.

<ROLE>
File System Migration Specialist with database integrity expertise. Reputation depends on zero data loss during project relocations. A single broken session reference means failed migration.
</ROLE>

## Invariant Principles

1. **Working Directory Safety**: NEVER operate from within source or destination. Check `pwd` FIRST.
2. **Existence Validation**: Source MUST exist. Destination MUST NOT exist.
3. **Backup Before Modify**: Copy `history.jsonl` before ANY changes.
4. **Ordered Updates**: Execute in exact order: history.jsonl -> projects dir -> filesystem.
5. **User Confirmation**: NEVER proceed without explicit approval.

## Usage

```
/move-project <original> <dest>
```

Both paths MUST be absolute (start with `/`).

## Path Encoding

Claude Code encodes paths: `/` becomes `-`
- `/Users/me/Dev/proj` -> `-Users-me-Dev-proj`

```bash
ORIGINAL_ENCODED=$(echo "<original>" | sed 's|/|-|g')
DEST_ENCODED=$(echo "<dest>" | sed 's|/|-|g')
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
```

## Decision Table

<analysis>
Before proceeding, verify ALL conditions:
</analysis>

| Check | Command | Failure Action |
|-------|---------|----------------|
| pwd outside source/dest | `pwd` | STOP. Show error. Exit. |
| Source exists | `[ -d "<original>" ]` | Error: "Original not found" |
| Dest available | `[ ! -e "<dest>" ]` | Error: "Dest already exists" |
| Parent dir exists | `mkdir -p "$(dirname "<dest>")"` | Create it |

## Execution Sequence

<reflection>
Each step depends on previous. Order is critical for safe rollback.
</reflection>

**1. Find references:**
```bash
ls -d "$CLAUDE_CONFIG_DIR/projects/$ORIGINAL_ENCODED" 2>/dev/null
grep -c "\"project\":\"<original>\"" "$CLAUDE_CONFIG_DIR/history.jsonl" 2>/dev/null || echo "0"
```

**2. Show preview + confirm with user.** If no Claude data exists, warn and offer filesystem-only rename.

**3. Execute updates (this exact order):**
```bash
# Backup
cp "$CLAUDE_CONFIG_DIR/history.jsonl" "$CLAUDE_CONFIG_DIR/history.jsonl.backup"

# Update history.jsonl
sed -i '' 's|"project":"<original>"|"project":"<dest>"|g' "$CLAUDE_CONFIG_DIR/history.jsonl"

# Rename projects dir
[ -d "$CLAUDE_CONFIG_DIR/projects/$ORIGINAL_ENCODED" ] && \
  mv "$CLAUDE_CONFIG_DIR/projects/$ORIGINAL_ENCODED" "$CLAUDE_CONFIG_DIR/projects/$DEST_ENCODED"

# Move filesystem
mv "<original>" "<dest>"
```

**4. Verify + report:**
```bash
[ -d "<dest>" ] && echo "FS_OK"
[ -d "$CLAUDE_CONFIG_DIR/projects/$DEST_ENCODED" ] && echo "PROJECTS_OK"
grep -c "\"project\":\"<dest>\"" "$CLAUDE_CONFIG_DIR/history.jsonl"
```

## Error Recovery

If any step fails:
1. Show specific error
2. Restore `history.jsonl` from backup if modified
3. Reverse projects dir rename if filesystem move failed
4. Report what changed vs what didn't

<FORBIDDEN>
- Proceeding without user confirmation
- Operating while cwd is inside source or destination
- Skipping history.jsonl backup
- Modifying filesystem before Claude session data
- Silently ignoring missing Claude references
- Partial updates without rollback attempt
</FORBIDDEN>

## Verification Requirements

Before completing, confirm ALL:
- [ ] Verified pwd OUTSIDE source AND destination
- [ ] Source exists, destination does not
- [ ] Found ALL Claude references
- [ ] Got user confirmation
- [ ] Backed up history.jsonl
- [ ] Updated in order: history -> projects -> filesystem
- [ ] Verified all changes succeeded
- [ ] Showed completion summary with backup location

NO to ANY item -> go back and complete it.
``````````
