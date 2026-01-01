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

## File Structure Reference

Claude Code stores session data in a specific structure:

```
~/.claude/                          # CLAUDE_CONFIG_DIR (default ~/.claude)
├── projects/                       # All project session data
│   └── {encoded-cwd}/              # One directory per project
│       └── {session-uuid}.jsonl    # Session files (JSONL format)
├── distilled/                      # Distilled session output
│   └── {encoded-cwd}/              # Mirrors projects structure
│       └── {slug}-{timestamp}.md   # Distilled summaries
└── scripts/
    └── distill_session.py          # Helper script for this command
```

**Path Encoding:**
- Working directory is encoded by replacing `/` with `-` and stripping the leading `-`
- Example: `/Users/alice/Development/my-project` becomes `Users-alice-Development-my-project`

**Session File Format:**
- JSONL (JSON Lines): one JSON object per line
- Each line is a message with fields: `uuid`, `parentUuid`, `type`, `message`, `timestamp`, `slug`, etc.
- `slug` field contains session name (e.g., `fancy-nibbling-sketch`)
- `type: "system", subtype: "compact_boundary"` marks compact points
- `isCompactSummary: true` marks compact summary messages

---

## Identifying Stuck Sessions

A session is likely stuck if ANY of these conditions are true:

| Indicator | How to Detect |
|-----------|---------------|
| "Prompt is too long" error | Search tail for `"Prompt is too long"` in assistant messages |
| Failed compact | `/compact` command in tail WITHOUT subsequent `compact_boundary` |
| API error at end | `"isApiErrorMessage": true` in last few messages |
| Manual rename with error hint | Slug or custom title contains: `error`, `stuck`, `fail`, `compact` |
| Large session without recent compact | Size > 2MB AND no `compact_boundary` in last 500 messages |

**Quick detection command:**
```bash
# Find sessions with "Prompt is too long" errors
grep -l "Prompt is too long" ~/.claude/projects/{encoded-cwd}/*.jsonl

# Find large sessions (likely need distillation)
ls -lhS ~/.claude/projects/{encoded-cwd}/*.jsonl | head -10
```

---

## Implementation

<PHASES>

### Phase 0: Session Discovery

**Step 1: Get project directory and list sessions**

The project directory maps the current working directory to an encoded path:

```python
import os

cwd = os.getcwd()
# Encode: /Users/alice/project → Users-alice-project
encoded = cwd.replace('/', '-').lstrip('-')
claude_config_dir = os.environ.get('CLAUDE_CONFIG_DIR') or os.path.expanduser('~/.claude')
project_dir = os.path.join(claude_config_dir, 'projects', encoded)
```

```bash
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
python3 "$CLAUDE_CONFIG_DIR/scripts/distill_session.py" list-sessions "$project_dir" --limit 5
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
python3 "$CLAUDE_CONFIG_DIR/scripts/distill_session.py" get-last-compact {session_file}
```

Store result. If `null`, start from line 0. If exists, start from `line_number + 2` (skip boundary and summary).

**Step 2: Get content after last compact (or from start)**

If last compact exists:

```bash
python3 "$CLAUDE_CONFIG_DIR/scripts/distill_session.py" get-content-after {session_file} --start-line {last_compact_line + 1}
```

Otherwise:

```bash
python3 "$CLAUDE_CONFIG_DIR/scripts/distill_session.py" get-content-from-start {session_file}
```

**Step 3: Calculate character count**

Count characters in the JSON output. If < 300,000 chars, skip chunking (use single subagent).

**Step 4: Calculate chunks (if needed)**

```bash
python3 "$CLAUDE_CONFIG_DIR/scripts/distill_session.py" split-by-char-limit {session_file} \
  --start-line {start_line} \
  --char-limit 300000
```

Store chunk boundaries: `[(start_1, end_1), (start_2, end_2), ...]`

### Phase 2: Parallel Summarization

**Step 1: Extract chunks**

For each chunk boundary `(start, end)`, extract content:

```bash
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
python3 "$CLAUDE_CONFIG_DIR/scripts/distill_session.py" extract-chunk {session_file} \
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

CRITICAL - PRESERVE WORKFLOW CONTINUITY:
7. What SKILLS or COMMANDS were being used? (e.g., /simplify, /implement-feature, /commit)
8. What SUBAGENTS were spawned, and what were their:
   - Agent IDs (if visible)
   - Assigned tasks/responsibilities
   - Skills/commands they were given
   - Status (running, completed, blocked)
9. What WORKFLOW PATTERN was in use?
   - Single-threaded (main agent doing everything)
   - Sequential delegation (one subagent at a time)
   - Parallel swarm (multiple subagents on discrete tasks)
   - Hierarchical (subagents spawning sub-subagents)

This information is VITAL for session continuation. Without it, the workflow cannot be resumed correctly.

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

VITAL - WORKFLOW CONTINUITY (without this, the session CANNOT be resumed correctly):
6. Preserve ALL active skills/commands that were in use (e.g., /simplify, /implement-feature)
7. Preserve ALL subagent responsibilities, IDs, and the skills/commands given to them
8. Preserve the WORKFLOW PATTERN (parallel swarm, sequential delegation, etc.)
9. The continuation protocol MUST instruct the new session to:
   - Resume using the SAME skills/commands
   - Check on or replace active subagents with SAME personas and skills
   - Continue the SAME workflow pattern, not start fresh

NOTE: Skills and commands (e.g., /implement-feature, /simplify, /execute-plan) are often THE SOURCE of workflow patterns. They define how work is organized, what subagents get spawned, and how tasks are delegated. If a skill was active, the new session MUST re-invoke that skill to restore the workflow - not try to manually recreate it. If a command was active, the new session must re-invoke that command with appropriate instructions for resuming the work. This applies to the main agent as well as any subagents.

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

---

## Error Handling

| Scenario | Response |
|----------|----------|
| No sessions found | Exit: "No sessions found for this project" |
| Session file unreadable | Skip session in listing, or abort if selected |
| Chunk summarization fails | Retry once, then apply partial results policy (20% threshold) |
| Synthesis fails | Output raw chunk summaries as fallback |
| Output directory not writable | Report error with path and suggest manual creation |
| Python script not found | Exit: "Helper script not found at {path}. Run install.sh to set up." |
| Single chunk exceeds context window | Truncate to 300k chars, add warning: "[TRUNCATED: chunk too large]" |
| > 20% chunks fail | Abort with error listing failed chunk ranges |

**Rollback Strategy:**
- Original session file is never modified
- Partial output files are kept (not deleted on error) for debugging
- Provide actionable error messages with file paths

**Risk Mitigation:**
- **Context Window Exceeded:** If a single message within a chunk exceeds context limits, truncate the message at 300k characters and add "[TRUNCATED: message too large for context window]" marker
- **Partial Results:** Mark missing chunks as "[CHUNK N FAILED - SUMMARIZATION ERROR]" in synthesis input
- **Minimum Viable Summary:** If <= 20% of chunks fail, proceed with partial synthesis; if > 20% fail, abort and recommend manual intervention

---

## When Tests Fail

If any test fails during implementation, invoke the `systematic-debugging` skill to diagnose the issue:

1. Run: `systematic-debugging` with test failure output
2. Follow the skill's hypothesis-driven workflow
3. Fix the root cause (not just symptoms)
4. Re-run tests to verify fix
5. Document the issue and resolution in commit message

---

## Multi-Project Usage

To distill sessions from projects OTHER than the current working directory:

1. **Find the encoded project path:**
   ```bash
   # List all projects with sessions
   ls ~/.claude/projects/

   # Example output:
   # -Users-alice-Development-my-project
   # -Users-alice-Development-other-project
   ```

2. **Provide the project path explicitly:**
   When asked which session to distill, you can specify sessions from any project by providing the full path.

3. **Parallel distillation of multiple projects:**
   To distill stuck sessions from multiple projects simultaneously, spawn parallel Task agents:
   ```
   Task("Distill project-a", "Distill session at ~/.claude/projects/-Users-.../abc.jsonl", "general-purpose")
   Task("Distill project-b", "Distill session at ~/.claude/projects/-Users-.../xyz.jsonl", "general-purpose")
   ```

---

## Notes

- Uses `~/.claude/scripts/distill_session.py` for all I/O operations
- Summaries generated via Task tool subagents (standard Claude Code behavior)
- Original session file is NEVER modified
- Output follows compact.md format exactly
- Character limit of 300k per chunk (~75k tokens) leaves safety buffer
- Chronological order is critical for synthesis quality
- AskUserQuestion tool format follows standard Claude Code tool interface
- Distill-session supersedes the old repair-session command (which has been removed)
