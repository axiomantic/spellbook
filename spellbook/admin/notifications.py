"""Notification queue for MCP session pull-based delivery.

Admin mutation handlers call enqueue() when events occur.
MCP tool handlers call drain() at the start of each tool call
to retrieve and deliver pending notifications via session.send_notification().

Uses bounded deque (max 100 per key) with oldest-dropped semantics.
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from typing import Optional

from spellbook.admin.events import Event, Subsystem

logger = logging.getLogger(__name__)


class NotificationScope:
    BROADCAST = "broadcast"  # All sessions
    NAMESPACE = "namespace"  # Sessions in matching project
    SESSION = "session"  # Specific session only
    ADMIN_ONLY = "admin_only"  # WebSocket subscribers only


def classify_event_scope(event: Event) -> str:
    """Determine notification routing scope for an event."""
    # Config and security mode changes broadcast to all
    if event.subsystem == Subsystem.CONFIG:
        return NotificationScope.BROADCAST
    if event.subsystem == Subsystem.SECURITY and event.event_type == "mode_changed":
        return NotificationScope.BROADCAST

    # Memory mutations scope to namespace
    if event.subsystem == Subsystem.MEMORY and event.namespace:
        return NotificationScope.NAMESPACE

    # Workflow state changes scope to specific session
    if event.subsystem == Subsystem.SESSION and event.session_id:
        return NotificationScope.SESSION

    # Everything else is admin-only (WebSocket subscribers)
    return NotificationScope.ADMIN_ONLY


@dataclass
class PendingNotification:
    """A notification waiting to be delivered to an MCP session."""

    subsystem: str
    event_type: str
    data: dict
    timestamp: str


class NotificationQueue:
    """In-memory notification queue for MCP session pull-based delivery.

    Keyed by (namespace, session_id, broadcast). Uses bounded deque
    (max 100 per key) with oldest-dropped semantics.
    """

    MAX_PER_KEY = 100

    def __init__(self):
        self._queues: dict[str, deque[PendingNotification]] = {}
        self._lock = asyncio.Lock()

    def _key(
        self,
        scope: str,
        namespace: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        if scope == NotificationScope.BROADCAST:
            return "broadcast"
        elif scope == NotificationScope.NAMESPACE and namespace:
            return f"ns:{namespace}"
        elif scope == NotificationScope.SESSION and session_id:
            return f"sess:{session_id}"
        return "broadcast"

    async def enqueue(self, event: Event) -> None:
        """Called by admin mutation handlers when events occur."""
        scope = classify_event_scope(event)
        if scope == NotificationScope.ADMIN_ONLY:
            return  # Only WebSocket subscribers get this

        notification = PendingNotification(
            subsystem=event.subsystem.value,
            event_type=event.event_type,
            data=event.data,
            timestamp=event.timestamp,
        )

        async with self._lock:
            if scope == NotificationScope.BROADCAST:
                key = self._key(scope)
                q = self._queues.setdefault(key, deque(maxlen=self.MAX_PER_KEY))
                q.append(notification)
            elif scope == NotificationScope.NAMESPACE:
                key = self._key(scope, namespace=event.namespace)
                q = self._queues.setdefault(key, deque(maxlen=self.MAX_PER_KEY))
                q.append(notification)
            elif scope == NotificationScope.SESSION:
                key = self._key(scope, session_id=event.session_id)
                q = self._queues.setdefault(key, deque(maxlen=self.MAX_PER_KEY))
                q.append(notification)

    async def drain(
        self, namespace: str, session_id: Optional[str] = None
    ) -> list[PendingNotification]:
        """Called by MCP tool handlers at the start of each tool call.

        Returns all pending notifications relevant to this session:
        - Broadcast notifications
        - Namespace-scoped notifications matching this namespace
        - Session-scoped notifications matching this session_id (if provided)

        Returned notifications are removed from the queue.
        """
        result: list[PendingNotification] = []

        async with self._lock:
            # Drain broadcast
            broadcast_key = "broadcast"
            if broadcast_key in self._queues:
                result.extend(self._queues.pop(broadcast_key))

            # Drain namespace-scoped
            ns_key = f"ns:{namespace}"
            if ns_key in self._queues:
                result.extend(self._queues.pop(ns_key))

            # Drain session-scoped
            if session_id:
                sess_key = f"sess:{session_id}"
                if sess_key in self._queues:
                    result.extend(self._queues.pop(sess_key))

        return result


# Singleton
notification_queue = NotificationQueue()
