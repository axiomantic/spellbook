"""Worker integration helper for swarm coordination.

This module provides a helper class that workers use to integrate with
the swarm coordination system. It handles dual-write behavior (writing
checkpoint marker files AND calling MCP backend tools).
"""
from pathlib import Path
from typing import Optional
import json
from datetime import datetime, timezone

from .backends import get_backend


class SwarmWorker:
    """Helper class for workers to integrate with swarm coordination.

    This class wraps MCP backend calls and provides dual-write behavior
    for checkpointing. Workers should use this class to:
    - Register with the swarm on startup
    - Report task progress as work completes
    - Report final completion when all work is done
    - Report errors when they occur

    The dual-write behavior ensures that even if the HTTP backend is
    unavailable, progress is checkpointed to disk for recovery.

    Example:
        worker = SwarmWorker(
            swarm_id="swarm-123",
            packet_id=1,
            packet_name="backend-api",
            worktree="/path/to/worktree",
            tasks_total=10
        )

        # Register on startup
        await worker.register()

        # Report each task
        await worker.report_progress("task-1", "Implement auth", "completed", commit="abc123")

        # Report completion
        await worker.report_complete("def456", tests_passed=True, review_passed=True)
    """

    def __init__(
        self,
        swarm_id: str,
        packet_id: int,
        packet_name: str,
        worktree: str,
        tasks_total: int
    ):
        """Initialize worker helper.

        Args:
            swarm_id: Unique identifier for the swarm
            packet_id: Packet ID number (positive integer)
            packet_name: Name of the packet (lowercase alphanumeric with hyphens)
            worktree: Absolute path to the worktree
            tasks_total: Total number of tasks in this packet
        """
        self.swarm_id = swarm_id
        self.packet_id = packet_id
        self.packet_name = packet_name
        self.worktree = worktree
        self.tasks_total = tasks_total
        self.tasks_completed = 0

    @property
    def checkpoint_path(self) -> Path:
        """Get path to checkpoint marker file.

        Returns:
            Path to checkpoint file in .spellbook/checkpoints/
        """
        checkpoint_dir = Path(self.worktree) / ".spellbook" / "checkpoints"
        return checkpoint_dir / f"packet-{self.packet_id}-{self.packet_name}.json"

    def _write_checkpoint(self, event: str, data: dict) -> None:
        """Write checkpoint marker file.

        This is the first part of dual-write behavior. The checkpoint is
        written BEFORE the HTTP call to ensure it persists even if the
        backend is unavailable.

        Args:
            event: Event type (registered, progress, complete, error)
            data: Event data to checkpoint
        """
        checkpoint = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "packet_id": self.packet_id,
            "packet_name": self.packet_name,
            "tasks_completed": self.tasks_completed,
            "tasks_total": self.tasks_total,
            **data
        }

        # Ensure directory exists
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        # Write checkpoint
        self.checkpoint_path.write_text(json.dumps(checkpoint, indent=2))

    async def register(self) -> dict:
        """Register with the swarm. Call this on startup.

        This performs dual-write:
        1. Writes checkpoint marker file
        2. Calls MCP backend register_worker

        Returns:
            Registration response from backend
        """
        # Dual-write: checkpoint FIRST, then backend call
        self._write_checkpoint("registered", {})

        backend = get_backend("mcp-streamable-http", {})
        return await backend.register_worker(
            swarm_id=self.swarm_id,
            packet_id=self.packet_id,
            packet_name=self.packet_name,
            tasks_total=self.tasks_total,
            worktree=self.worktree
        )

    async def report_progress(
        self,
        task_id: str,
        task_name: str,
        status: str = "completed",
        commit: Optional[str] = None
    ) -> dict:
        """Report task progress. Increments tasks_completed counter.

        This performs dual-write:
        1. Increments tasks_completed counter
        2. Writes checkpoint marker file
        3. Calls MCP backend report_progress

        Args:
            task_id: Unique identifier for the task
            task_name: Human-readable task name
            status: Task status (started, completed, failed)
            commit: Optional git commit SHA

        Returns:
            Progress response from backend
        """
        # Increment counter FIRST
        if status == "completed":
            self.tasks_completed += 1

        # Dual-write: checkpoint FIRST, then backend call
        checkpoint_data = {
            "task_id": task_id,
            "task_name": task_name,
            "status": status
        }
        if commit is not None:
            checkpoint_data["commit"] = commit

        self._write_checkpoint("progress", checkpoint_data)

        backend = get_backend("mcp-streamable-http", {})
        return await backend.report_progress(
            swarm_id=self.swarm_id,
            packet_id=self.packet_id,
            task_id=task_id,
            task_name=task_name,
            status=status,
            tasks_completed=self.tasks_completed,
            tasks_total=self.tasks_total,
            commit=commit
        )

    async def report_complete(
        self,
        final_commit: str,
        tests_passed: bool = True,
        review_passed: bool = True
    ) -> dict:
        """Signal worker completion.

        This performs dual-write:
        1. Writes checkpoint marker file
        2. Calls MCP backend report_complete

        Args:
            final_commit: Final commit SHA (7-40 hex characters)
            tests_passed: Whether tests passed
            review_passed: Whether review passed

        Returns:
            Completion response from backend
        """
        # Dual-write: checkpoint FIRST, then backend call
        self._write_checkpoint("complete", {
            "final_commit": final_commit,
            "tests_passed": tests_passed,
            "review_passed": review_passed
        })

        backend = get_backend("mcp-streamable-http", {})
        return await backend.report_complete(
            swarm_id=self.swarm_id,
            packet_id=self.packet_id,
            final_commit=final_commit,
            tests_passed=tests_passed,
            review_passed=review_passed
        )

    async def report_error(
        self,
        task_id: str,
        error_type: str,
        message: str,
        recoverable: bool = False
    ) -> dict:
        """Report an error.

        This performs dual-write:
        1. Writes checkpoint marker file
        2. Calls MCP backend report_error

        Args:
            task_id: Task identifier where error occurred
            error_type: Type of error (network_error, test_failure, etc.)
            message: Error message (max 5000 characters)
            recoverable: Whether the error is recoverable

        Returns:
            Error response from backend
        """
        # Dual-write: checkpoint FIRST, then backend call
        self._write_checkpoint("error", {
            "task_id": task_id,
            "error_type": error_type,
            "message": message,
            "recoverable": recoverable
        })

        backend = get_backend("mcp-streamable-http", {})
        return await backend.report_error(
            swarm_id=self.swarm_id,
            packet_id=self.packet_id,
            task_id=task_id,
            error_type=error_type,
            message=message,
            recoverable=recoverable
        )
