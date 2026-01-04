#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "fastmcp",
# ]
# ///
"""
Spellbook MCP Server - Session management tools for Claude Code.

Provides three MCP tools:
- find_session: Search sessions by name (case-insensitive)
- split_session: Calculate chunk boundaries for session content
- list_sessions: List recent sessions with metadata and samples
"""

from fastmcp import FastMCP
from pathlib import Path
from typing import List, Dict, Any
import os
import json
import sys

# Add script directory to sys.path to allow imports when run directly
# This fixes "ImportError: attempted relative import with no known parent package"
# when the server is executed as a standalone script by Gemini CLI.
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from path_utils import get_project_dir
from session_ops import (
    split_by_char_limit,
    list_sessions_with_samples,
)
from skill_ops import find_skills, load_skill

mcp = FastMCP("spellbook")

# Default directories to search for skills
# Personal skills > Spellbook skills
def get_skill_dirs() -> List[Path]:
    dirs = []

    # Personal skills (e.g. ~/.opencode/skills or ~/.config/opencode/skills)
    # Use standard XDG config or home dir patterns
    home = Path.home()
    dirs.append(home / ".config" / "opencode" / "skills")
    dirs.append(home / ".opencode" / "skills")
    dirs.append(home / ".codex" / "skills")

    # Spellbook skills (this repo)
    # Assume this server is running from inside spellbook/spellbook_mcp
    # So ../skills
    repo_root = Path(__file__).parent.parent
    dirs.append(repo_root / "skills")

    # Check CLAUDE_CONFIG_DIR
    claude_config = os.environ.get("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    dirs.append(Path(claude_config) / "skills")

    return [d for d in dirs if d.exists()]

@mcp.tool()
def find_session(name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Find sessions by name using case-insensitive substring matching.

    Searches both the session slug and custom title (if set via /rename).
    Returns sessions sorted by last activity (most recent first).

    Args:
        name: Search query (case-insensitive substring)
        limit: Maximum results to return (default 10)

    Returns:
        List of session metadata dictionaries matching the search query
    """
    project_dir = get_project_dir()

    # Return empty list if project directory doesn't exist (new project)
    if not project_dir.exists():
        return []

    # Load all sessions using list_sessions_with_samples
    # Use a high limit to get all sessions, then filter
    all_sessions = list_sessions_with_samples(str(project_dir), limit=1000)

    # Normalize search query
    name_lower = name.strip().lower()

    # Filter by name match in slug or custom_title
    # Empty string matches all (as per design doc)
    if not name_lower:
        matches = all_sessions
    else:
        matches = [
            s for s in all_sessions
            if (s.get('slug') and name_lower in s['slug'].lower())
            or (s.get('custom_title') and name_lower in s['custom_title'].lower())
        ]

    # Already sorted by last_activity in list_sessions_with_samples
    return matches[:limit]


@mcp.tool()
def split_session(session_path: str, start_line: int, char_limit: int) -> List[List[int]]:
    """
    Calculate chunk boundaries for a session that respect message boundaries.

    Returns list of [start_line, end_line] pairs where end_line is exclusive.
    Always splits at message boundaries (never mid-message).

    Args:
        session_path: Absolute path to .jsonl session file
        start_line: Starting line number (0-indexed)
        char_limit: Maximum characters per chunk

    Returns:
        List of [start, end] chunk boundaries

    Raises:
        FileNotFoundError: If session file doesn't exist
        ValueError: If start_line out of bounds or char_limit invalid
    """
    # Delegate to session_ops implementation
    # Already returns List[List[int]]
    return split_by_char_limit(session_path, start_line, char_limit)


@mcp.tool()
def list_sessions(limit: int = 5) -> List[Dict[str, Any]]:
    """
    List recent sessions for current project with rich metadata and content samples.

    Auto-detects project directory from current working directory.
    Returns sessions sorted by last activity (most recent first).

    Args:
        limit: Maximum sessions to return (default 5)

    Returns:
        List of session metadata dictionaries
    """
    project_dir = get_project_dir()

    # Return empty list if project directory doesn't exist (new project)
    if not project_dir.exists():
        return []

    return list_sessions_with_samples(str(project_dir), limit)

@mcp.tool()
def find_spellbook_skills() -> str:
    """
    List all available Spellbook skills with their descriptions.
    
    Returns:
        JSON string of list of {name, description} objects.
    """
    dirs = get_skill_dirs()
    skills = find_skills(dirs)
    # Simplify output for LLM consumption (just name and description)
    simplified = [{"name": s["name"], "description": s["description"]} for s in skills]
    return json.dumps(simplified, indent=2)

@mcp.tool()
def use_spellbook_skill(skill_name: str) -> str:
    """
    Load the content of a specific Spellbook skill.
    
    Args:
        skill_name: The name of the skill to load (e.g., 'scientific-debugging')
        
    Returns:
        The full markdown content of the skill instructions.
    """
    dirs = get_skill_dirs()
    try:
        return load_skill(skill_name, dirs)
    except ValueError as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run()
