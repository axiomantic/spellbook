"""Shared type definitions for execution mode."""

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Task:
    """Individual task within a work packet."""
    id: str
    description: str
    files: List[str]
    acceptance: str

@dataclass
class Packet:
    """Work packet containing tasks for a single track."""
    format_version: str
    feature: str
    track: int
    worktree: str
    branch: str
    tasks: List[Task]
    body: str

@dataclass
class Track:
    """Track metadata in manifest."""
    id: int
    name: str
    packet: str
    worktree: str
    branch: str
    status: str  # "pending" | "in_progress" | "complete"
    depends_on: List[int]
    checkpoint: Optional[str] = None
    completion: Optional[str] = None

@dataclass
class Manifest:
    """Manifest describing all tracks for a feature."""
    format_version: str
    feature: str
    created: str
    project_root: str
    design_doc: str
    impl_plan: str
    execution_mode: str
    tracks: List[Track]
    shared_setup_commit: str
    merge_strategy: str
    post_merge_qa: List[str]

@dataclass
class Checkpoint:
    """Checkpoint file for resuming track execution."""
    format_version: str
    track: int
    last_completed_task: str
    commit: str
    timestamp: str
    next_task: Optional[str] = None

@dataclass
class CompletionMarker:
    """Completion marker file indicating track is done."""
    format_version: str
    status: str
    commit: str
    timestamp: str
