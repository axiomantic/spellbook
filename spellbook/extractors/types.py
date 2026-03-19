"""Shared type definitions for all extractors.

ALL Phase 2 extractors MUST:
1. Import types from this file
2. Return values matching these type definitions
3. NOT invent their own dict structures
"""

from typing import TypedDict, Optional, List, Literal


class TodoItem(TypedDict):
    """Single todo item structure matching TodoWrite tool format."""

    content: str
    status: Literal["pending", "in_progress", "completed"]
    activeForm: str


class ToolAction(TypedDict):
    """Single tool invocation for position tracking."""

    tool: str
    primary_arg: str
    timestamp: str
    success: Optional[bool]


# Type aliases for extractor return values
TodoList = List[TodoItem]
ActiveSkill = Optional[str]  # Skill name or None
SkillPhase = Optional[str]  # Phase description or None
Persona = Optional[str]  # "fun:{persona}" or "tarot" or None
RecentFiles = List[str]  # List of absolute file paths
Position = List[ToolAction]  # Last N tool actions
WorkflowPattern = Literal["test-driven-development", "parallel-agents", "sequential"]


class Soul(TypedDict):
    """Complete soul structure returned by extract_soul()."""

    todos: TodoList
    active_skill: ActiveSkill
    skill_phase: SkillPhase
    persona: Persona
    recent_files: RecentFiles
    exact_position: Position
    workflow_pattern: WorkflowPattern
