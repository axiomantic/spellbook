"""Event bus for real-time admin notifications.

In-process asyncio pub/sub with per-subscriber bounded queues.
When a subscriber's queue is full, the oldest event is dropped
to prevent unbounded memory growth.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class Subsystem(str, Enum):
    MEMORY = "memory"
    SECURITY = "security"
    SESSION = "session"
    CONFIG = "config"
    FRACTAL = "fractal"
    SWARM = "swarm"
    EXPERIMENT = "experiment"
    FORGE = "forge"


@dataclass
class Event:
    subsystem: Subsystem
    event_type: str
    data: dict
    timestamp: str = field(
        default_factory=lambda: __import__("datetime")
        .datetime.now(__import__("datetime").timezone.utc)
        .isoformat()
    )
    namespace: Optional[str] = None  # For namespace-scoped routing
    session_id: Optional[str] = None  # For session-specific routing


class EventBus:
    """In-process asyncio pub/sub with per-subscriber bounded queues."""

    QUEUE_SIZE = 1000

    def __init__(self):
        self._subscribers: dict[str, asyncio.Queue] = {}
        self._dropped_counts: dict[str, int] = {}
        self._total_dropped: int = 0
        self._lock = asyncio.Lock()

    async def subscribe(self, subscriber_id: str) -> asyncio.Queue:
        """Register a subscriber and return their event queue."""
        async with self._lock:
            queue: asyncio.Queue = asyncio.Queue(maxsize=self.QUEUE_SIZE)
            self._subscribers[subscriber_id] = queue
            self._dropped_counts[subscriber_id] = 0
            return queue

    async def unsubscribe(self, subscriber_id: str) -> None:
        """Remove a subscriber."""
        async with self._lock:
            self._subscribers.pop(subscriber_id, None)
            self._dropped_counts.pop(subscriber_id, None)

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers.

        If a subscriber's queue is full, the oldest event is dropped.
        Subscriber exceptions cause removal (error isolation).
        """
        async with self._lock:
            dead_subscribers = []
            for sub_id, queue in self._subscribers.items():
                try:
                    if queue.full():
                        try:
                            queue.get_nowait()  # Drop oldest
                        except asyncio.QueueEmpty:
                            pass
                        self._dropped_counts[sub_id] = (
                            self._dropped_counts.get(sub_id, 0) + 1
                        )
                        self._total_dropped += 1
                    queue.put_nowait(event)
                except Exception:
                    logger.error(
                        f"Subscriber {sub_id} error, removing", exc_info=True
                    )
                    dead_subscribers.append(sub_id)

            for sub_id in dead_subscribers:
                self._subscribers.pop(sub_id, None)
                self._dropped_counts.pop(sub_id, None)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def total_dropped_events(self) -> int:
        return self._total_dropped


# Singleton
event_bus = EventBus()


def publish_sync(
    event: Event,
    bus: Optional[EventBus] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> None:
    """Thread-safe wrapper for publishing events from sync MCP tool handlers.

    Schedules publish() on the given (or running) event loop from any thread.
    Fire-and-forget: errors are logged but never propagated to the caller.
    """
    target_bus = bus or event_bus
    try:
        target_loop = loop or asyncio.get_running_loop()
    except RuntimeError:
        # No running loop available, try to get the main loop
        try:
            target_loop = asyncio.get_event_loop()
        except RuntimeError:
            logger.warning("No event loop available for publish_sync, dropping event")
            return

    if target_loop.is_running():
        # Schedule from another thread
        asyncio.run_coroutine_threadsafe(target_bus.publish(event), target_loop)
    else:
        # Loop exists but isn't running (unusual, but handle gracefully)
        logger.warning("Event loop not running for publish_sync, dropping event")
