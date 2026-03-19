"""Notification queue tests: enqueue/drain, scope routing, queue limits."""

import pytest

from spellbook.admin.events import Event, Subsystem
from spellbook.admin.notifications import (
    NotificationQueue,
    NotificationScope,
    classify_event_scope,
)


class TestClassifyEventScope:
    def test_config_events_are_broadcast(self):
        event = Event(subsystem=Subsystem.CONFIG, event_type="updated", data={})
        assert classify_event_scope(event) == NotificationScope.BROADCAST

    def test_security_mode_changed_is_broadcast(self):
        event = Event(
            subsystem=Subsystem.SECURITY, event_type="mode_changed", data={}
        )
        assert classify_event_scope(event) == NotificationScope.BROADCAST

    def test_security_other_is_admin_only(self):
        event = Event(
            subsystem=Subsystem.SECURITY, event_type="event_logged", data={}
        )
        assert classify_event_scope(event) == NotificationScope.ADMIN_ONLY

    def test_memory_with_namespace_is_namespace_scoped(self):
        event = Event(
            subsystem=Subsystem.MEMORY,
            event_type="created",
            data={},
            namespace="my-project",
        )
        assert classify_event_scope(event) == NotificationScope.NAMESPACE

    def test_memory_without_namespace_is_admin_only(self):
        event = Event(subsystem=Subsystem.MEMORY, event_type="created", data={})
        assert classify_event_scope(event) == NotificationScope.ADMIN_ONLY

    def test_session_with_session_id_is_session_scoped(self):
        event = Event(
            subsystem=Subsystem.SESSION,
            event_type="state_updated",
            data={},
            session_id="sess-123",
        )
        assert classify_event_scope(event) == NotificationScope.SESSION

    def test_session_without_session_id_is_admin_only(self):
        event = Event(
            subsystem=Subsystem.SESSION, event_type="state_updated", data={}
        )
        assert classify_event_scope(event) == NotificationScope.ADMIN_ONLY

    def test_other_subsystem_is_admin_only(self):
        event = Event(subsystem=Subsystem.FRACTAL, event_type="graph_created", data={})
        assert classify_event_scope(event) == NotificationScope.ADMIN_ONLY


class TestNotificationQueue:
    @pytest.mark.asyncio
    async def test_enqueue_broadcast_then_drain(self):
        q = NotificationQueue()
        event = Event(
            subsystem=Subsystem.CONFIG, event_type="updated", data={"key": "x"}
        )
        await q.enqueue(event)

        # Any session can drain broadcast events
        notifications = await q.drain("any-namespace")
        assert len(notifications) == 1
        assert notifications[0].subsystem == "config"
        assert notifications[0].event_type == "updated"

    @pytest.mark.asyncio
    async def test_drain_removes_notifications(self):
        q = NotificationQueue()
        event = Event(
            subsystem=Subsystem.CONFIG, event_type="updated", data={}
        )
        await q.enqueue(event)

        # First drain gets it
        first = await q.drain("ns")
        assert len(first) == 1

        # Second drain gets nothing
        second = await q.drain("ns")
        assert len(second) == 0

    @pytest.mark.asyncio
    async def test_namespace_scoped_only_matches(self):
        q = NotificationQueue()
        event = Event(
            subsystem=Subsystem.MEMORY,
            event_type="created",
            data={},
            namespace="project-a",
        )
        await q.enqueue(event)

        # Wrong namespace gets nothing
        wrong_ns = await q.drain("project-b")
        assert len(wrong_ns) == 0

        # Right namespace gets it
        right_ns = await q.drain("project-a")
        assert len(right_ns) == 1

    @pytest.mark.asyncio
    async def test_session_scoped_only_matches(self):
        q = NotificationQueue()
        event = Event(
            subsystem=Subsystem.SESSION,
            event_type="state_updated",
            data={},
            session_id="sess-123",
        )
        await q.enqueue(event)

        # No session_id gets nothing
        without_sess = await q.drain("ns")
        assert len(without_sess) == 0

        # Wrong session_id gets nothing
        wrong_sess = await q.drain("ns", session_id="sess-456")
        assert len(wrong_sess) == 0

        # Right session_id gets it
        right_sess = await q.drain("ns", session_id="sess-123")
        assert len(right_sess) == 1

    @pytest.mark.asyncio
    async def test_admin_only_not_enqueued(self):
        q = NotificationQueue()
        # Admin-only event (fractal without namespace/session)
        event = Event(
            subsystem=Subsystem.FRACTAL, event_type="graph_created", data={}
        )
        await q.enqueue(event)

        # Should not appear in drain
        notifications = await q.drain("any-ns")
        assert len(notifications) == 0

    @pytest.mark.asyncio
    async def test_bounded_deque_drops_oldest(self):
        q = NotificationQueue()
        q.MAX_PER_KEY = 3  # Small for testing

        for i in range(5):
            event = Event(
                subsystem=Subsystem.CONFIG,
                event_type=f"event-{i}",
                data={"i": i},
            )
            await q.enqueue(event)

        notifications = await q.drain("ns")
        # Only last 3 should remain (bounded deque)
        assert len(notifications) == 3
        assert notifications[0].event_type == "event-2"
        assert notifications[1].event_type == "event-3"
        assert notifications[2].event_type == "event-4"

    @pytest.mark.asyncio
    async def test_drain_combines_broadcast_and_namespace(self):
        q = NotificationQueue()

        # Broadcast event
        await q.enqueue(
            Event(subsystem=Subsystem.CONFIG, event_type="config_change", data={})
        )
        # Namespace-scoped event
        await q.enqueue(
            Event(
                subsystem=Subsystem.MEMORY,
                event_type="memory_created",
                data={},
                namespace="my-proj",
            )
        )

        notifications = await q.drain("my-proj")
        assert len(notifications) == 2

    @pytest.mark.asyncio
    async def test_drain_combines_all_scopes(self):
        q = NotificationQueue()

        await q.enqueue(
            Event(subsystem=Subsystem.CONFIG, event_type="broadcast_event", data={})
        )
        await q.enqueue(
            Event(
                subsystem=Subsystem.MEMORY,
                event_type="ns_event",
                data={},
                namespace="proj",
            )
        )
        await q.enqueue(
            Event(
                subsystem=Subsystem.SESSION,
                event_type="sess_event",
                data={},
                session_id="s-1",
            )
        )

        notifications = await q.drain("proj", session_id="s-1")
        assert len(notifications) == 3

    @pytest.mark.asyncio
    async def test_empty_drain_returns_empty_list(self):
        q = NotificationQueue()
        notifications = await q.drain("ns")
        assert notifications == []
