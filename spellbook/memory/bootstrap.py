"""MEMORY.md regenerator for bridging Claude Code auto-memory with spellbook.

Generates a static MEMORY.md that directs the model to use spellbook MCP
tools for memory operations, breaking the feedback loop where DB content
was rendered into MEMORY.md and then re-captured.
"""

from pathlib import Path
from typing import Optional

from spellbook.core.db import get_db_path
from spellbook.core.path_utils import encode_cwd
from spellbook.memory.tools import do_log_event


MEMORY_MD_TEMPLATE = """\
# Spellbook Memory System

The contents of this file are managed by spellbook's memory system.
Any notes you write here will be automatically captured and stored.

## Retrieving Knowledge

Use these MCP tools to access project memories:

- `memory_recall(query="topic")` - search for specific knowledge
- `memory_recall(query="", limit=20)` - recent important memories
- `memory_recall(file_path="/path/to/file.py")` - memories about a specific file
- `memory_recall(tags="api,auth")` - filter by tags

## Storing Knowledge

- `memory_store(content="...", type="project", kind="fact", tags="tag1,tag2")`

Types: `project`, `user`, `feedback`, `reference`
Kinds: `fact`, `rule`, `convention`, `preference`, `decision`, `antipattern`

## Syncing and Verification

- `memory_sync(changed_files="src/main.py,src/config.py")` - find memories affected by code changes
- `memory_verify(memory_path="/path/to/memory.md")` - fact-check a single memory
- `memory_review_events()` - review pending raw events for synthesis

## How It Works

- MEMORY.md is refreshed at the start of each session
- Any content you write here is automatically captured by the bridge hook and stored in spellbook's structured memory (file-based markdown with grep/QMD search, branch scoring, importance ranking)
- Use `memory_recall` instead of re-reading this file for past context
- Use `memory_store` for important knowledge you want to persist across sessions
"""


def generate_memory_md(**kwargs) -> str:
    """Generate the MEMORY.md content.

    Returns a static redirect template that instructs the model
    to use spellbook MCP tools for memory operations. Accepts
    **kwargs for backward compatibility but ignores them.
    """
    return MEMORY_MD_TEMPLATE


def _resolve_auto_memory_dir(project_path: str) -> Optional[Path]:
    """Resolve the Claude Code auto-memory directory for a project.

    Claude Code uses: ~/.claude/projects/<project-encoded>/memory/
    where project-encoded = path with leading / removed, slashes -> dashes,
    prefixed with a dash.
    """
    home = Path.home()
    encoded = project_path.lstrip("/").replace("/", "-")

    # Primary: with leading dash (Claude Code's format)
    memory_dir = home / ".claude" / "projects" / f"-{encoded}" / "memory"
    if memory_dir.is_dir():
        return memory_dir

    # Fallback: without leading dash
    alt_dir = home / ".claude" / "projects" / encoded / "memory"
    if alt_dir.is_dir():
        return alt_dir

    return None


def _bootstrap_existing_memory_md(
    memory_dir: Path, db_path: str, namespace: str
) -> None:
    """One-time: capture existing MEMORY.md content before first regeneration."""
    marker = memory_dir / ".spellbook-bridge-initialized"
    if marker.exists():
        return

    memory_md = memory_dir / "MEMORY.md"
    if memory_md.exists():
        content = memory_md.read_text(encoding="utf-8")
        if content.strip() and "spellbook-managed" not in content:
            do_log_event(
                db_path=db_path,
                session_id="bootstrap",
                project=namespace,
                tool_name="auto_memory_bridge",
                subject=str(memory_md),
                summary=content[:10000],
                tags="auto-memory,bridge,bootstrap,memory.md",
                event_type="auto_memory_bridge",
                branch="",
            )

    marker.write_text("initialized", encoding="utf-8")


def regenerate_memory_md_for_project(project_path: str) -> None:
    """Regenerate MEMORY.md for a project's auto-memory directory.

    Resolves the auto-memory directory path, bootstraps existing content
    if needed, generates the static template, and writes the file.
    Fail-open: exceptions do not propagate.
    """
    try:
        memory_dir = _resolve_auto_memory_dir(project_path)
        if not memory_dir:
            return

        db_path = str(get_db_path())
        namespace = encode_cwd(project_path)

        # One-time bootstrap of pre-existing content
        _bootstrap_existing_memory_md(memory_dir, db_path, namespace)

        content = generate_memory_md()

        memory_md_path = memory_dir / "MEMORY.md"
        memory_md_path.write_text(content, encoding="utf-8")
    except Exception:
        pass  # Fail-open: never block session init
