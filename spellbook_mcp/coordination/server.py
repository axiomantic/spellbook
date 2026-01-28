"""FastAPI coordination server for swarm coordination."""
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from datetime import UTC, datetime
from pathlib import Path
import asyncio
from typing import AsyncGenerator
import json

from .state import StateManager
from .protocol import (
    RegisterRequest, ProgressRequest, CompleteRequest, ErrorRequest,
    SwarmCreateResponse, RegisterResponse, ProgressResponse,
    CompleteResponse, ErrorResponse, SwarmStatus, WorkerStatus,
    HealthResponse
)
from .retry import classify_error, ErrorCategory, RetryPolicy


class CoordinationServer:
    """FastAPI-based coordination server for swarm management."""

    def __init__(self, database_path: str, port: int = 7432, host: str = "127.0.0.1"):
        """
        Initialize coordination server.

        Args:
            database_path: Path to SQLite database
            port: HTTP server port
            host: HTTP server host
        """
        self.database_path = database_path
        self.port = port
        self.host = host
        self.state = StateManager(database_path)
        self.app = FastAPI(title="Spellbook Coordination Server", version="2.0.0")
        self.retry_policy = RetryPolicy()
        self.start_time = datetime.now(UTC)

        self._setup_routes()

    def _setup_routes(self):
        """Setup FastAPI routes."""

        @self.app.post("/swarm/create", response_model=SwarmCreateResponse, status_code=status.HTTP_201_CREATED)
        def create_swarm(
            feature: str,
            manifest_path: str,
            auto_merge: bool = False,
            notify_on_complete: bool = True
        ):
            """Create a new swarm."""
            swarm_id = self.state.create_swarm(feature, manifest_path, auto_merge, notify_on_complete)
            return SwarmCreateResponse(
                swarm_id=swarm_id,
                endpoint=f"http://{self.host}:{self.port}/swarm/{swarm_id}",
                created_at=datetime.now(UTC),
                auto_merge=auto_merge,
                notify_on_complete=notify_on_complete
            )

        @self.app.post("/swarm/{swarm_id}/register", response_model=RegisterResponse)
        def register_worker(swarm_id: str, request: RegisterRequest):
            """Register a worker with the swarm."""
            try:
                self.state.get_swarm(swarm_id)
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Swarm not found: {swarm_id}")

            try:
                self.state.register_worker(
                    swarm_id=swarm_id,
                    packet_id=request.packet_id,
                    packet_name=request.packet_name,
                    tasks_total=request.tasks_total,
                    worktree=request.worktree
                )
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    raise HTTPException(status_code=409, detail=f"Worker already registered: {request.packet_id}")
                raise

            return RegisterResponse(
                registered=True,
                packet_id=request.packet_id,
                packet_name=request.packet_name,
                swarm_id=swarm_id,
                registered_at=datetime.now(UTC)
            )

        @self.app.post("/swarm/{swarm_id}/progress", response_model=ProgressResponse)
        def report_progress(swarm_id: str, request: ProgressRequest):
            """Report worker progress."""
            try:
                self.state.get_swarm(swarm_id)
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Swarm not found: {swarm_id}")

            self.state.update_progress(
                swarm_id=swarm_id,
                packet_id=request.packet_id,
                task_id=request.task_id,
                task_name=request.task_name,
                status=request.status,
                tasks_completed=request.tasks_completed,
                tasks_total=request.tasks_total,
                commit=request.commit
            )

            return ProgressResponse(
                acknowledged=True,
                packet_id=request.packet_id,
                task_id=request.task_id,
                tasks_completed=request.tasks_completed,
                tasks_total=request.tasks_total,
                timestamp=datetime.now(UTC)
            )

        @self.app.post("/swarm/{swarm_id}/complete", response_model=CompleteResponse)
        def report_complete(swarm_id: str, request: CompleteRequest):
            """Report worker completion."""
            try:
                swarm = self.state.get_swarm(swarm_id)
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Swarm not found: {swarm_id}")

            self.state.mark_complete(
                swarm_id=swarm_id,
                packet_id=request.packet_id,
                final_commit=request.final_commit,
                tests_passed=request.tests_passed,
                review_passed=request.review_passed
            )

            # Check if swarm is now complete
            updated_swarm = self.state.get_swarm(swarm_id)
            swarm_complete = updated_swarm["status"] == "complete"

            # Count remaining workers
            # This is a simplified calculation - in production would query workers table
            remaining_workers = 0 if swarm_complete else 1

            return CompleteResponse(
                acknowledged=True,
                packet_id=request.packet_id,
                final_commit=request.final_commit,
                completed_at=datetime.now(UTC),
                swarm_complete=swarm_complete,
                remaining_workers=remaining_workers
            )

        @self.app.post("/swarm/{swarm_id}/error", response_model=ErrorResponse)
        def report_error(swarm_id: str, request: ErrorRequest):
            """Report worker error."""
            try:
                self.state.get_swarm(swarm_id)
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Swarm not found: {swarm_id}")

            self.state.record_error(
                swarm_id=swarm_id,
                packet_id=request.packet_id,
                task_id=request.task_id,
                error_type=request.error_type,
                message=request.message,
                recoverable=request.recoverable
            )

            # Determine if retry should be scheduled
            category = classify_error(request.error_type)
            retry_scheduled = category == ErrorCategory.RECOVERABLE
            retry_in_seconds = self.retry_policy.get_retry_delay(1) if retry_scheduled else None

            return ErrorResponse(
                acknowledged=True,
                packet_id=request.packet_id,
                error_logged=True,
                retry_scheduled=retry_scheduled,
                retry_in_seconds=retry_in_seconds
            )

        @self.app.get("/swarm/{swarm_id}/status", response_model=SwarmStatus)
        def get_swarm_status(swarm_id: str):
            """Get current swarm status."""
            try:
                swarm = self.state.get_swarm(swarm_id)
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Swarm not found: {swarm_id}")

            # Get events to build worker status
            # For MVP, we'll return minimal status
            # Full implementation would query workers table and build detailed status
            return SwarmStatus(
                swarm_id=swarm_id,
                status=swarm["status"],
                workers_registered=0,  # Simplified for MVP
                workers_complete=0,
                workers_failed=0,
                ready_for_merge=swarm["status"] == "complete",
                workers=[],
                created_at=datetime.fromisoformat(swarm["created_at"].rstrip("Z")),
                last_update=datetime.fromisoformat(swarm["updated_at"].rstrip("Z"))
            )

        @self.app.get("/swarm/{swarm_id}/events")
        async def get_events_sse(swarm_id: str, since_event_id: int = 0):
            """Get events via Server-Sent Events (SSE)."""
            try:
                self.state.get_swarm(swarm_id)
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Swarm not found: {swarm_id}")

            async def event_generator() -> AsyncGenerator[str, None]:
                """Generate SSE events."""
                last_id = since_event_id

                while True:
                    events = self.state.get_events(swarm_id, since_event_id=last_id)

                    for event in events:
                        # Format as SSE
                        event_data = {
                            "event_type": event["event_type"],
                            "packet_id": event.get("packet_id"),
                            "task_id": event.get("task_id"),
                            "commit": event.get("commit"),
                            "created_at": event["created_at"]
                        }

                        yield f"id: {event['event_id']}\n"
                        yield f"event: {event['event_type']}\n"
                        yield f"data: {json.dumps(event_data)}\n\n"

                        last_id = event["event_id"]

                    # Check if swarm is complete
                    swarm = self.state.get_swarm(swarm_id)
                    if swarm["status"] in ("complete", "failed"):
                        break

                    # Wait before checking for new events
                    await asyncio.sleep(2)

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )

        @self.app.get("/health", response_model=HealthResponse)
        def health_check():
            """Health check endpoint."""
            uptime = (datetime.now(UTC) - self.start_time).total_seconds()

            return HealthResponse(
                status="healthy",
                uptime_seconds=int(uptime),
                active_swarms=0,  # Simplified for MVP
                total_workers=0,
                version="2.0.0"
            )

    def run(self):
        """Run the server (for testing/development)."""
        import uvicorn
        uvicorn.run(self.app, host=self.host, port=self.port)
