"""MCP Streamable HTTP backend for coordination."""
import httpx
import json
from typing import Dict, Any, AsyncGenerator, Optional
from .base import CoordinationBackend


class MCPStreamableHTTPBackend(CoordinationBackend):
    """HTTP backend that connects to local CoordinationServer."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize HTTP backend.

        Args:
            config: Configuration dictionary with host and port
        """
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 7432)
        self.base_url = f"http://{self.host}:{self.port}"

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
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/swarm/create",
                params={
                    "feature": feature,
                    "manifest_path": manifest_path,
                    "auto_merge": auto_merge,
                    "notify_on_complete": True
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["swarm_id"]

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
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/swarm/{swarm_id}/register",
                json={
                    "packet_id": packet_id,
                    "packet_name": packet_name,
                    "tasks_total": tasks_total,
                    "worktree": worktree
                }
            )
            response.raise_for_status()
            return response.json()

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
        async with httpx.AsyncClient() as client:
            payload = {
                "packet_id": packet_id,
                "task_id": task_id,
                "task_name": task_name,
                "status": status,
                "tasks_completed": tasks_completed,
                "tasks_total": tasks_total
            }
            if commit is not None:
                payload["commit"] = commit

            response = await client.post(
                f"{self.base_url}/swarm/{swarm_id}/progress",
                json=payload
            )
            response.raise_for_status()
            return response.json()

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
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/swarm/{swarm_id}/complete",
                json={
                    "packet_id": packet_id,
                    "final_commit": final_commit,
                    "tests_passed": tests_passed,
                    "review_passed": review_passed
                }
            )
            response.raise_for_status()
            return response.json()

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
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/swarm/{swarm_id}/error",
                json={
                    "packet_id": packet_id,
                    "task_id": task_id,
                    "error_type": error_type,
                    "message": message,
                    "recoverable": recoverable
                }
            )
            response.raise_for_status()
            return response.json()

    async def get_status(self, swarm_id: str) -> Dict[str, Any]:
        """
        Get current swarm status.

        Args:
            swarm_id: Swarm identifier

        Returns:
            Swarm status data
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/swarm/{swarm_id}/status"
            )
            response.raise_for_status()
            return response.json()

    async def subscribe_events(self, swarm_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Subscribe to swarm events via Server-Sent Events.

        Args:
            swarm_id: Swarm identifier

        Yields:
            Event data dictionaries
        """
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "GET",
                f"{self.base_url}/swarm/{swarm_id}/events",
                params={"since_event_id": 0}
            ) as response:
                current_event = {}
                async for line in response.aiter_lines():
                    line = line.strip()

                    if not line:
                        # Empty line signals end of event
                        if current_event:
                            yield current_event
                            current_event = {}
                        continue

                    if line.startswith("id:"):
                        current_event["id"] = line[3:].strip()
                    elif line.startswith("event:"):
                        current_event["event"] = line[6:].strip()
                    elif line.startswith("data:"):
                        data_str = line[5:].strip()
                        try:
                            data = json.loads(data_str)
                            current_event.update(data)
                        except json.JSONDecodeError:
                            current_event["raw_data"] = data_str
