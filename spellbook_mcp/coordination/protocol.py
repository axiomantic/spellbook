"""Request/response schemas for coordination protocol."""
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from typing import Literal, Optional
import os


class RegisterRequest(BaseModel):
    """Worker registration request."""
    packet_id: int = Field(gt=0, description="Packet ID, positive integer")
    packet_name: str = Field(
        min_length=1,
        max_length=255,
        pattern=r"^[a-z0-9-]+$",
        description="Packet name, lowercase alphanumeric with hyphens"
    )
    tasks_total: int = Field(gt=0, le=1000, description="Total tasks, 1-1000")
    worktree: str = Field(min_length=1, description="Worktree path, must be absolute")


class ProgressRequest(BaseModel):
    """Worker progress update request."""
    packet_id: int = Field(gt=0)
    task_id: str = Field(min_length=1, max_length=255)
    task_name: str = Field(min_length=1, max_length=500)
    status: Literal["started", "completed", "failed"]
    commit: Optional[str] = Field(
        default=None,
        pattern=r"^[a-f0-9]{7,40}$",
        description="Git commit SHA"
    )
    tasks_completed: int = Field(ge=0)
    tasks_total: int = Field(gt=0)

    @model_validator(mode='after')
    def validate_tasks_completed(self):
        """Validate tasks_completed does not exceed tasks_total."""
        if self.tasks_completed > self.tasks_total:
            raise ValueError("tasks_completed cannot exceed tasks_total")
        return self


class CompleteRequest(BaseModel):
    """Worker completion request."""
    packet_id: int = Field(gt=0)
    final_commit: str = Field(pattern=r"^[a-f0-9]{7,40}$", description="Final commit SHA")
    tests_passed: bool
    review_passed: bool


class ErrorRequest(BaseModel):
    """Worker error report request."""
    packet_id: int = Field(gt=0)
    task_id: str = Field(min_length=1, max_length=255)
    error_type: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=5000)
    recoverable: bool


class SwarmCreateResponse(BaseModel):
    """Response for swarm creation."""
    swarm_id: str
    endpoint: str
    created_at: datetime
    auto_merge: bool
    notify_on_complete: bool


class RegisterResponse(BaseModel):
    """Response for worker registration."""
    registered: bool
    packet_id: int
    packet_name: str
    swarm_id: str
    registered_at: datetime


class ProgressResponse(BaseModel):
    """Response for progress update."""
    acknowledged: bool
    packet_id: int
    task_id: str
    tasks_completed: int
    tasks_total: int
    timestamp: datetime


class CompleteResponse(BaseModel):
    """Response for worker completion."""
    acknowledged: bool
    packet_id: int
    final_commit: str
    completed_at: datetime
    swarm_complete: bool
    remaining_workers: int


class ErrorResponse(BaseModel):
    """Response for error report."""
    acknowledged: bool
    packet_id: int
    error_logged: bool
    retry_scheduled: bool
    retry_in_seconds: Optional[int] = None


class WorkerStatus(BaseModel):
    """Status of a single worker."""
    packet_id: int
    packet_name: str
    status: str
    tasks_completed: int
    tasks_total: int
    last_update: datetime


class SwarmStatus(BaseModel):
    """Status of a swarm."""
    swarm_id: str
    status: Literal["created", "running", "complete", "failed"]
    workers_registered: int
    workers_complete: int
    workers_failed: int
    ready_for_merge: bool
    workers: list[WorkerStatus]
    created_at: datetime
    last_update: datetime


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    uptime_seconds: int
    active_swarms: int
    total_workers: int
    version: str
