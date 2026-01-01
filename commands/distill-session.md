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

[Phase implementations will be added in subsequent tasks]

</PHASES>
