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

### Phase 2: Parallel Summarization

**Step 1: Extract chunks**

For each chunk boundary `(start, end)`, extract content:

```bash
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
python3 "$CLAUDE_CONFIG_DIR/scripts/distill-session.py" extract-chunk {session_file} \
  --start-line {start} \
  --end-line {end}
```

Store each chunk's JSON content.

**Step 2: Craft chunk summarization prompts**

For each chunk N (1-indexed):

```
You are summarizing a portion of a Claude Code conversation.

This is chunk {N} of {total_chunks}.

Your job: Extract key information from this chunk following this structure:

1. What was the user trying to accomplish?
2. What approach was taken?
3. What decisions were made and why?
4. What files were created/modified?
5. What errors occurred and how were they resolved?
6. What work remains incomplete?

Be thorough but concise. Another AI will synthesize your summary with others.

---

CONVERSATION CHUNK:

{chunk_content}
```

**Step 3: Spawn parallel subagents**

Use Task tool to spawn N subagents in parallel (ONE message with ALL Task calls):

```
Task("Chunk 1 Summarizer", "{prompt_for_chunk_1}", "researcher")
Task("Chunk 2 Summarizer", "{prompt_for_chunk_2}", "researcher")
Task("Chunk 3 Summarizer", "{prompt_for_chunk_3}", "researcher")
...
```

**Step 4: Collect summaries**

Wait for all Task outputs. Store as:
- Summary 1 (chunk 1)
- Summary 2 (chunk 2)
- ...

If any subagent fails: Retry once. If still fails, report partial results and warn user.

**Partial Results Policy:** If <= 20% of chunks fail summarization, proceed with synthesis using available summaries and mark missing chunks. If > 20% fail, abort and report error.

### Phase 3: Synthesis

**Step 1: Read compact.md format**

```bash
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
cat "$CLAUDE_CONFIG_DIR/commands/compact.md"
```

Store the template content.

**Step 2: Assemble ordered summaries**

Create ordered list:
1. Summary 0 (last compact summary, if exists)
2. Summary 1 (first chunk)
3. Summary 2 (second chunk)
4. ...

**Step 3: Craft synthesis prompt**

```
You are synthesizing multiple conversation summaries into one unified summary.

You will receive {N} summaries in CHRONOLOGICAL ORDER:
- Summary 0 (if present) covers the earliest part of the conversation
- Summary 1 covers the next part
- ...and so on

Your job: Combine these into ONE coherent summary following the compact.md format below.

CRITICAL RULES:
1. Preserve chronological flow - early context informs later work
2. Deduplicate redundant information
3. Preserve ALL pending work items from the most recent summary
4. Preserve ALL user corrections and behavioral guidance
5. The continuation protocol should reflect the FINAL state

---

COMPACT.MD FORMAT TO FOLLOW:

{compact_md_content}

---

SUMMARIES TO SYNTHESIZE (in chronological order):

Summary 0 (Prior Compact):
{summary_0_or_none}

Summary 1:
{summary_1}

Summary 2:
{summary_2}

...
```

**Step 4: Spawn synthesis subagent**

```
Task("Synthesis Agent", "{synthesis_prompt}", "researcher")
```

**Step 5: Collect final summary**

Store the synthesized output.

If synthesis fails: Fall back to outputting raw chunk summaries with warning.

**Note on Missing Chunks:** When partial results are used (from Phase 2), missing chunks are marked in synthesis input as "[CHUNK N FAILED - SUMMARIZATION ERROR]".

### Phase 4: Output

**Step 1: Generate output path**

```python
import os
from datetime import datetime

cwd = os.getcwd()
project_encoded = cwd.replace('/', '-').lstrip('-')
claude_config_dir = os.environ.get('CLAUDE_CONFIG_DIR') or os.path.expanduser('~/.claude')
distilled_dir = os.path.join(claude_config_dir, 'distilled', project_encoded)

# Create directory if needed
os.makedirs(distilled_dir, exist_ok=True)

# Generate filename
timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
slug = selected_session['slug'] or 'session'
filename = f"{slug}-{timestamp}.md"
output_path = os.path.join(distilled_dir, filename)
```

**Step 2: Write summary to file**

```python
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(final_summary)
```

**Step 3: Report completion**

```
Distillation complete!

Summary saved to: {output_path}

To continue work in a new session:
1. Start new Claude Code session
2. Type: "continue work from {output_path}"

Original session preserved at: {session_file}
```

</PHASES>
