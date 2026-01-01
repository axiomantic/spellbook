# Distill Session

Extract knowledge from oversized Claude Code sessions into a standalone summary document.

## When to Use

**Symptoms:**
- Session too large to compact (context window exceeded)
- Need to preserve knowledge but start fresh
- `/compact` fails or is stuck

**What this command does:**
- Discovers sessions in current project
- Chunks content to fit in context
- Summarizes chunks in parallel via subagents
- Synthesizes into unified summary following compact.md format
- Outputs markdown file ready for new session

## How It Works

1. **Session Discovery** - Lists recent sessions with AI-generated descriptions
2. **User Selection** - Pick which session to distill
3. **Analysis** - Determine if chunking needed
4. **Parallel Summarization** - Spawn subagents for each chunk
5. **Synthesis** - Combine summaries chronologically
6. **Output** - Write to `~/.claude/distilled/{project}/{slug}-{timestamp}.md`

---

## Implementation

<PHASES>

### Phase 0: Session Discovery

**Step 1: Get project directory and list sessions**

```python
import os

cwd = os.getcwd()
encoded = cwd.replace('/', '-').lstrip('-')
claude_config_dir = os.environ.get('CLAUDE_CONFIG_DIR') or os.path.expanduser('~/.claude')
project_dir = os.path.join(claude_config_dir, 'projects', encoded)
```

```bash
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
python3 "$CLAUDE_CONFIG_DIR/scripts/distill-session.py" list-sessions "$project_dir" --limit 5
```

**Step 2: Generate holistic descriptions**

For each session in the list, use the content samples to generate a holistic description:

**Prompt template:**

```
Based on these samples from a Claude Code session, generate a concise holistic description (1-2 sentences) of what the user was working on:

First user message: {first_user_message}

Last compact summary (if exists): {last_compact_summary}

Recent messages:
{recent_messages}

Respond with ONLY the description, no preamble.
```

Store descriptions in a list alongside session metadata.

**Step 3: Present options to user**

Use AskUserQuestion:

```json
{
  "questions": [{
    "question": "Which session should I distill?",
    "header": "Found {N} recent sessions (most recent first)",
    "options": [
      {
        "label": "{slug}",
        "description": "{holistic_description}\nMessages: {message_count} | Chars: {char_count} | Compacts: {compact_count}\nLast activity: {last_activity}"
      }
    ],
    "multiSelect": false
  }]
}
```

**Step 4: Handle selection**

Store selected session path for Phase 1.

If no sessions found: Exit with "No sessions found in this project."

### Phase 1: Analyze & Chunk

**Step 1: Get last compact summary (Summary 0)**

```bash
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
python3 "$CLAUDE_CONFIG_DIR/scripts/distill-session.py" get-last-compact {session_file}
```

Store result. If `null`, start from line 0. If exists, start from `line_number + 2` (skip boundary and summary).

**Step 2: Get content after last compact (or from start)**

If last compact exists:

```bash
python3 "$CLAUDE_CONFIG_DIR/scripts/distill-session.py" get-content-after {session_file} --start-line {last_compact_line + 1}
```

Otherwise:

```bash
python3 "$CLAUDE_CONFIG_DIR/scripts/distill-session.py" get-content-from-start {session_file}
```

**Step 3: Calculate character count**

Count characters in the JSON output. If < 300,000 chars, skip chunking (use single subagent).

**Step 4: Calculate chunks (if needed)**

```bash
python3 "$CLAUDE_CONFIG_DIR/scripts/distill-session.py" split-by-char-limit {session_file} \
  --start-line {start_line} \
  --char-limit 300000
```

Store chunk boundaries: `[(start_1, end_1), (start_2, end_2), ...]`

</PHASES>
