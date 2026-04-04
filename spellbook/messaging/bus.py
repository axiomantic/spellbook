"""In-memory message bus for cross-session communication.

Provides bounded asyncio queues per session, correlation tracking with
TTL sweep, and broadcast delivery. Thread safety via asyncio.Lock.
"""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from spellbook.core.auth import load_token
from spellbook.core.path_utils import get_spellbook_config_dir
from spellbook.messaging.bridge import MessageBridge

logger = logging.getLogger(__name__)

QUEUE_SIZE = 256
DEFAULT_CORRELATION_TTL = 60  # seconds


@dataclass
class MessageEnvelope:
    """Wire format for all messages."""

    id: str
    sender: str
    recipient: str
    payload: dict
    timestamp: str
    message_type: str  # "direct" | "broadcast" | "reply"
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    ttl: int = DEFAULT_CORRELATION_TTL

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sender": self.sender,
            "recipient": self.recipient,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "message_type": self.message_type,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "ttl": self.ttl,
        }


@dataclass
class SessionRegistration:
    """A registered session with its message queue."""

    alias: str
    queue: asyncio.Queue
    registered_at: str


@dataclass
class PendingCorrelation:
    """Tracks a pending request/reply correlation."""

    correlation_id: str
    sender: str
    created_at: float  # monotonic time
    ttl: int


_DISCONNECT = object()
"""Sentinel value placed into a session's queue to signal SSE stream shutdown."""


class MessageBus:
    """In-memory message bus for cross-session communication.

    Thread safety: all mutations protected by asyncio.Lock.
    Queue semantics: bounded, error-on-full (not drop-oldest).
    Correlation tracking: pending requests with TTL, cleaned on access.
    """

    def __init__(self, queue_size: int = QUEUE_SIZE):
        self._sessions: dict[str, SessionRegistration] = {}
        self._pending_correlations: dict[str, PendingCorrelation] = {}
        self._bridges: dict[str, MessageBridge] = {}
        # Lock is created eagerly. This is safe because all async methods run
        # in the same event loop. The shutdown path bypasses the lock directly
        # (see server.py shutdown()) since atexit runs in a new event loop.
        self._lock = asyncio.Lock()
        self._queue_size = queue_size
        # Stats
        self._total_sent = 0
        self._total_delivered = 0
        self._total_errors = 0

    # --- Registration ---

    async def register(
        self,
        alias: str,
        enable_sse: bool = True,
        force: bool = False,
        session_id: str = "",
    ) -> SessionRegistration:
        """Register a session with the given alias.

        Args:
            alias: Unique session name.
            enable_sse: If True, spawn a MessageBridge for real-time delivery.
            force: If True, replace existing registration. Puts _DISCONNECT
                sentinel into old queue (for SSE cleanup), discards old
                registration, and logs a warning.
            session_id: Caller's session identifier. Written to a marker file
                so the hook only drains inboxes belonging to its own session.

        Raises ValueError if alias is already taken and force=False.
        """
        async with self._lock:
            return self._register_locked(alias, enable_sse, session_id, force=force)

    def _register_locked(
        self,
        alias: str,
        enable_sse: bool,
        session_id: str,
        force: bool = False,
    ) -> SessionRegistration:
        """Register while caller holds self._lock. Not async-safe on its own.

        Args:
            alias: Unique session name.
            enable_sse: If True, spawn a MessageBridge for real-time delivery.
            session_id: Caller's session identifier.
            force: If True, replace existing registration.

        Returns:
            SessionRegistration for the newly registered session.

        Raises:
            ValueError: If alias is taken and force=False.
        """
        if alias in self._sessions:
            if not force:
                raise ValueError(f"Alias already registered: {alias}")
            # Force: tear down old registration
            old_reg = self._sessions[alias]
            logger.warning(f"Force re-registering alias: {alias}")
            try:
                old_reg.queue.put_nowait(_DISCONNECT)
            except asyncio.QueueFull:
                pass  # Best-effort sentinel
            # Stop old bridge if present
            old_bridge = self._bridges.pop(alias, None)
            if old_bridge is not None:
                old_bridge.stop()

        reg = SessionRegistration(
            alias=alias,
            queue=asyncio.Queue(maxsize=self._queue_size),
            registered_at=datetime.now(timezone.utc).isoformat(),
        )
        self._sessions[alias] = reg

        # Spawn bridge inside the lock to prevent race conditions
        if enable_sse:
            self._start_bridge(alias)

        # Write session_id marker so the hook only drains this session's inboxes
        if session_id:
            self._write_session_marker(alias, session_id)

        return reg

    async def register_with_suffix(
        self,
        base_alias: str,
        session_id: str = "",
        max_suffix: int = 100,
        enable_sse: bool = True,
    ) -> tuple[str, bool]:
        """Register with automatic suffix for collision handling.

        If base_alias is available, registers it directly.
        If base_alias is taken by the SAME session_id, force-replaces (compaction).
        If base_alias is taken by a DIFFERENT session, tries base_alias-2,
        base_alias-3, ... up to base_alias-{max_suffix}.

        All logic runs inside self._lock for atomicity.

        Args:
            base_alias: Preferred alias (already slugified/truncated).
            session_id: Caller's session identifier for compaction detection.
            max_suffix: Maximum suffix number to try before falling back to UUID.
            enable_sse: Whether to spawn a MessageBridge.

        Returns:
            (actual_alias, was_force_replaced) tuple.

        Raises:
            RuntimeError: If all suffix slots exhausted AND UUID fallback fails.
        """
        async with self._lock:
            # Case 1: base_alias is free
            if base_alias not in self._sessions:
                self._register_locked(base_alias, enable_sse, session_id)
                return (base_alias, False)

            # Case 2: same session re-registering (compaction)
            existing_session_id = self._read_session_marker(base_alias)
            if session_id and existing_session_id == session_id:
                self._register_locked(base_alias, enable_sse, session_id, force=True)
                return (base_alias, True)

            # Case 3: different session, try suffixes
            for i in range(2, max_suffix + 1):
                candidate = f"{base_alias}-{i}"
                if len(candidate) > 64:
                    break  # Would exceed alias max length
                if candidate not in self._sessions:
                    self._register_locked(candidate, enable_sse, session_id)
                    return (candidate, False)
                # Check if this suffix is owned by same session
                marker = self._read_session_marker(candidate)
                if session_id and marker == session_id:
                    self._register_locked(candidate, enable_sse, session_id, force=True)
                    return (candidate, True)

            # Case 4: all suffixes exhausted, use UUID fragment
            fallback = f"{base_alias[:40]}-{uuid.uuid4().hex[:8]}"
            self._register_locked(fallback, enable_sse, session_id)
            return (fallback, False)

    def _write_session_marker(self, alias: str, session_id: str) -> None:
        """Write a .session_id marker so the hook only drains this session's inboxes."""
        alias_dir = get_spellbook_config_dir() / "messaging" / alias
        alias_dir.mkdir(parents=True, exist_ok=True)
        marker = alias_dir / ".session_id"
        try:
            marker.write_text(session_id)
        except OSError:
            logger.warning("Failed to write session marker for alias %s", alias)

    def _read_session_marker(self, alias: str) -> Optional[str]:
        """Read session_id from marker file for an existing registration.

        Args:
            alias: The session alias whose marker to read.

        Returns:
            The session_id string, or None if missing/empty/unreadable.
        """
        marker = get_spellbook_config_dir() / "messaging" / alias / ".session_id"
        try:
            text = marker.read_text().strip()
            return text or None
        except (FileNotFoundError, OSError):
            return None

    def _remove_session_marker(self, alias: str) -> None:
        """Remove the .session_id marker for the given alias."""
        marker = get_spellbook_config_dir() / "messaging" / alias / ".session_id"
        try:
            marker.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove session marker for alias %s", alias)

    def _start_bridge(self, alias: str) -> None:
        """Start a MessageBridge for the given alias."""
        host = os.environ.get("SPELLBOOK_MCP_HOST", "127.0.0.1")
        port = os.environ.get("SPELLBOOK_MCP_PORT", "8765")
        server_url = f"http://{host}:{port}"
        token = load_token()

        inbox_dir = get_spellbook_config_dir() / "messaging" / alias / "inbox"
        bridge = MessageBridge(
            alias=alias,
            server_url=server_url,
            token=token,
            inbox_dir=inbox_dir,
        )
        bridge.start()
        self._bridges[alias] = bridge

    async def unregister(self, alias: str) -> bool:
        """Unregister a session. Returns True if it existed."""
        async with self._lock:
            removed = self._sessions.pop(alias, None)
            if removed is not None:
                # Put disconnect sentinel for SSE cleanup
                try:
                    removed.queue.put_nowait(_DISCONNECT)
                except asyncio.QueueFull:
                    pass  # Best-effort sentinel
            # Clean up bridge
            bridge = self._bridges.pop(alias, None)
            if bridge is not None:
                bridge.stop()
            # Remove session marker
            self._remove_session_marker(alias)
            # Clean up any pending correlations from this session
            expired = [
                cid
                for cid, pc in self._pending_correlations.items()
                if pc.sender == alias
            ]
            for cid in expired:
                del self._pending_correlations[cid]
            return removed is not None

    async def list_sessions(self) -> list[dict]:
        """Return list of registered sessions (alias + registered_at)."""
        async with self._lock:
            return [
                {"alias": reg.alias, "registered_at": reg.registered_at}
                for reg in self._sessions.values()
            ]

    # --- Sending ---

    async def send(
        self,
        sender: str,
        recipient: str,
        payload: dict,
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        ttl: int = DEFAULT_CORRELATION_TTL,
    ) -> dict:
        """Send a direct message. Returns delivery status."""
        async with self._lock:
            if sender not in self._sessions:
                return {"ok": False, "error": "sender_not_registered"}

            target = self._sessions.get(recipient)
            if target is None:
                self._total_errors += 1
                return {
                    "ok": False,
                    "error": "recipient_not_found",
                    "recipient": recipient,
                }

            envelope = self._make_envelope(
                sender=sender,
                recipient=recipient,
                payload=payload,
                message_type="direct",
                correlation_id=correlation_id,
                reply_to=reply_to,
                ttl=ttl,
            )

            # Track correlation if present
            if correlation_id:
                self._sweep_expired_correlations()
                self._pending_correlations[correlation_id] = PendingCorrelation(
                    correlation_id=correlation_id,
                    sender=sender,
                    created_at=asyncio.get_running_loop().time(),
                    ttl=ttl,
                )

            try:
                target.queue.put_nowait(envelope)
                self._total_sent += 1
                self._total_delivered += 1
                return {"ok": True, "message_id": envelope.id}
            except asyncio.QueueFull:
                self._total_errors += 1
                return {
                    "ok": False,
                    "error": "recipient_queue_full",
                    "recipient": recipient,
                }

    async def broadcast(
        self,
        sender: str,
        payload: dict,
        exclude_sender: bool = True,
    ) -> dict:
        """Broadcast to all registered sessions. Returns delivery stats."""
        async with self._lock:
            if sender not in self._sessions:
                return {"ok": False, "error": "sender_not_registered"}

            delivered = 0
            failed = 0
            errors = []

            envelope = self._make_envelope(
                sender=sender,
                recipient="*",
                payload=payload,
                message_type="broadcast",
            )

            for alias, reg in self._sessions.items():
                if exclude_sender and alias == sender:
                    continue

                try:
                    reg.queue.put_nowait(envelope)
                    delivered += 1
                except asyncio.QueueFull:
                    failed += 1
                    errors.append({"alias": alias, "error": "queue_full"})

            self._total_sent += delivered
            self._total_delivered += delivered
            self._total_errors += failed

            return {
                "ok": True,
                "delivered_count": delivered,
                "failed_count": failed,
                "errors": errors if errors else None,
            }

    async def reply(
        self,
        sender: str,
        correlation_id: str,
        payload: dict,
    ) -> dict:
        """Send a reply to a pending correlation. Routes to original sender."""
        async with self._lock:
            self._sweep_expired_correlations()

            pending = self._pending_correlations.pop(correlation_id, None)
            if pending is None:
                return {
                    "ok": False,
                    "error": "correlation_not_found_or_expired",
                    "correlation_id": correlation_id,
                }

            original_sender = pending.sender
            target = self._sessions.get(original_sender)
            if target is None:
                self._total_errors += 1
                return {
                    "ok": False,
                    "error": "original_sender_disconnected",
                    "recipient": original_sender,
                }

            envelope = self._make_envelope(
                sender=sender,
                recipient=original_sender,
                payload=payload,
                message_type="reply",
                correlation_id=correlation_id,
            )

            try:
                target.queue.put_nowait(envelope)
                self._total_sent += 1
                self._total_delivered += 1
                return {"ok": True, "message_id": envelope.id}
            except asyncio.QueueFull:
                self._total_errors += 1
                return {
                    "ok": False,
                    "error": "recipient_queue_full",
                    "recipient": original_sender,
                }

    # --- Receiving ---

    async def poll(self, alias: str, max_messages: int = 10) -> tuple[list[dict], int]:
        """Drain up to max_messages from the session's queue.

        Returns:
            (messages, remaining) where remaining is the queue size read
            atomically right after draining.
        """
        async with self._lock:
            reg = self._sessions.get(alias)
            if reg is None:
                return [], 0
            queue = reg.queue

        messages = []
        for _ in range(max_messages):
            try:
                envelope = queue.get_nowait()
                if envelope is _DISCONNECT:
                    break
                messages.append(envelope.to_dict())
            except asyncio.QueueEmpty:
                break
        remaining = queue.qsize()
        return messages, remaining

    async def get_queue(self, alias: str) -> Optional[asyncio.Queue]:
        """Get the raw queue for SSE streaming. Returns None if not registered."""
        async with self._lock:
            reg = self._sessions.get(alias)
            return reg.queue if reg else None

    # --- Stats ---

    async def stats(self) -> dict:
        """Return bus statistics, sweeping expired correlations first."""
        async with self._lock:
            self._sweep_expired_correlations()
            return {
                "sessions_registered": len(self._sessions),
                "pending_correlations": len(self._pending_correlations),
                "total_sent": self._total_sent,
                "total_delivered": self._total_delivered,
                "total_errors": self._total_errors,
            }

    # --- Internal ---

    def _make_envelope(self, **kwargs) -> MessageEnvelope:
        """Create a new MessageEnvelope with auto-generated id and timestamp."""
        return MessageEnvelope(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            **kwargs,
        )

    def _sweep_expired_correlations(self) -> int:
        """Remove expired correlations. Returns count removed. Caller holds lock."""
        now = asyncio.get_running_loop().time()
        expired = [
            cid
            for cid, pc in self._pending_correlations.items()
            if (now - pc.created_at) > pc.ttl
        ]
        for cid in expired:
            del self._pending_correlations[cid]
        return len(expired)


# Module-level singleton
message_bus = MessageBus()
