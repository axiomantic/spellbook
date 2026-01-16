"""Extract structured session state (soul) from transcript."""

import json
from collections import deque
from typing import Dict, Any, List
from pathlib import Path

from .extractors.todos import extract_todos
from .extractors.skill import extract_active_skill
from .extractors.skill_phase import extract_skill_phase
from .extractors.persona import extract_persona
from .extractors.files import extract_recent_files
from .extractors.position import extract_position
from .extractors.workflow import extract_workflow_pattern
from .extractors.types import Soul


def read_jsonl(path: str, max_messages: int = 200) -> List[Dict[str, Any]]:
    """Read last N messages from JSONL transcript.

    Uses deque with maxlen for memory efficiency - only keeps
    the most recent max_messages in memory at any time.

    Args:
        path: Path to .jsonl file
        max_messages: Maximum messages to return (from end of file)

    Returns:
        List of message dicts, limited to last max_messages
    """
    messages: deque[Dict[str, Any]] = deque(maxlen=max_messages)
    file_path = Path(path)

    if not file_path.exists():
        return list(messages)

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                messages.append(msg)
            except json.JSONDecodeError:
                # Skip malformed lines
                continue

    return list(messages)


def extract_soul(transcript_path: str) -> Soul:
    """Extract complete soul from session transcript.

    Reads last 200 messages and extracts all 7 components.

    Args:
        transcript_path: Path to session .jsonl file

    Returns:
        Soul dict with keys:
        - todos: List of active todo dicts
        - active_skill: Skill name or None
        - skill_phase: Phase description or None
        - persona: Persona string or None
        - recent_files: List of file paths
        - exact_position: List of tool action dicts
        - workflow_pattern: Workflow string
    """
    messages = read_jsonl(transcript_path, max_messages=200)

    return {
        "todos": extract_todos(messages),
        "active_skill": extract_active_skill(messages),
        "skill_phase": extract_skill_phase(messages),
        "persona": extract_persona(messages),
        "recent_files": extract_recent_files(messages),
        "exact_position": extract_position(messages),
        "workflow_pattern": extract_workflow_pattern(messages)
    }
