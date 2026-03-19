"""Base class for coordination backends."""
from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator, Optional


class CoordinationBackend(ABC):
    """Abstract base class for coordination backends."""

    @abstractmethod
    async def create_swarm(self, feature: str, manifest_path: str, auto_merge: bool) -> str:
        """
        Create new swarm.

        Args:
            feature: Feature name
            manifest_path: Path to manifest file
            auto_merge: Whether to auto-merge on completion

        Returns:
            swarm_id: Unique identifier for the swarm
        """
        pass

    @abstractmethod
    async def register_worker(
        self,
        swarm_id: str,
        packet_id: int,
        packet_name: str,
        tasks_total: int,
        worktree: str
    ) -> Dict[str, Any]:
        """
        Register worker with swarm.

        Args:
            swarm_id: Swarm identifier
            packet_id: Packet ID number
            packet_name: Name of the packet
            tasks_total: Total number of tasks
            worktree: Path to worktree

        Returns:
            Registration response data
        """
        pass

    @abstractmethod
    async def report_progress(
        self,
        swarm_id: str,
        packet_id: int,
        task_id: str,
        task_name: str,
        status: str,
        tasks_completed: int,
        tasks_total: int,
        commit: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Report task progress.

        Args:
            swarm_id: Swarm identifier
            packet_id: Packet ID number
            task_id: Task identifier
            task_name: Name of the task
            status: Task status (started, completed, failed)
            tasks_completed: Number of tasks completed
            tasks_total: Total number of tasks
            commit: Optional git commit SHA

        Returns:
            Progress response data
        """
        pass

    @abstractmethod
    async def report_complete(
        self,
        swarm_id: str,
        packet_id: int,
        final_commit: str,
        tests_passed: bool,
        review_passed: bool
    ) -> Dict[str, Any]:
        """
        Report worker completion.

        Args:
            swarm_id: Swarm identifier
            packet_id: Packet ID number
            final_commit: Final commit SHA
            tests_passed: Whether tests passed
            review_passed: Whether review passed

        Returns:
            Completion response data
        """
        pass

    @abstractmethod
    async def report_error(
        self,
        swarm_id: str,
        packet_id: int,
        task_id: str,
        error_type: str,
        message: str,
        recoverable: bool
    ) -> Dict[str, Any]:
        """
        Report worker error.

        Args:
            swarm_id: Swarm identifier
            packet_id: Packet ID number
            task_id: Task identifier
            error_type: Type of error
            message: Error message
            recoverable: Whether error is recoverable

        Returns:
            Error response data
        """
        pass

    @abstractmethod
    async def get_status(self, swarm_id: str) -> Dict[str, Any]:
        """
        Get current swarm status.

        Args:
            swarm_id: Swarm identifier

        Returns:
            Swarm status data
        """
        pass

    @abstractmethod
    async def subscribe_events(self, swarm_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Subscribe to swarm events (async generator for SSE).

        Args:
            swarm_id: Swarm identifier

        Yields:
            Event data dictionaries
        """
        pass
        # Make this a generator by using yield (even though abstract)
        yield  # type: ignore


# Backend registry
BACKENDS: Dict[str, type[CoordinationBackend]] = {}


def register_backend(name: str, backend_class: type[CoordinationBackend]):
    """
    Register a backend implementation.

    Args:
        name: Backend name
        backend_class: Backend class (subclass of CoordinationBackend)
    """
    BACKENDS[name] = backend_class


def get_backend(config: Dict[str, Any]) -> CoordinationBackend:
    """
    Get backend instance from configuration.

    Args:
        config: Configuration dictionary with 'backend' key

    Returns:
        Backend instance

    Raises:
        ValueError: If backend type unknown or config missing 'backend' key
    """
    if "backend" not in config:
        raise ValueError("Configuration must include 'backend' key")

    backend_name = config["backend"]

    if backend_name not in BACKENDS:
        raise ValueError(f"Unknown backend type: {backend_name}")

    backend_class = BACKENDS[backend_name]
    return backend_class(config)
