"""Event bus unit tests: pub/sub, backpressure, subscriber lifecycle, publish_sync."""

import asyncio
import threading

import pytest

from spellbook.admin.events import Event, EventBus, Subsystem, event_bus


@pytest.mark.asyncio
async def test_publish_reaches_subscriber():
    bus = EventBus()
    queue = await bus.subscribe("test-sub")
    event = Event(subsystem=Subsystem.MEMORY, event_type="created", data={"id": "1"})
    await bus.publish(event)
    received = queue.get_nowait()
    assert received.event_type == "created"
    assert received.data == {"id": "1"}


@pytest.mark.asyncio
async def test_publish_reaches_multiple_subscribers():
    bus = EventBus()
    q1 = await bus.subscribe("sub-1")
    q2 = await bus.subscribe("sub-2")
    event = Event(subsystem=Subsystem.MEMORY, event_type="created", data={})
    await bus.publish(event)
    assert not q1.empty()
    assert not q2.empty()
    assert q1.get_nowait().event_type == "created"
    assert q2.get_nowait().event_type == "created"


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    bus = EventBus()
    queue = await bus.subscribe("test-sub")
    await bus.unsubscribe("test-sub")
    event = Event(subsystem=Subsystem.MEMORY, event_type="created", data={})
    await bus.publish(event)
    assert queue.empty()


@pytest.mark.asyncio
async def test_bounded_queue_drops_oldest():
    bus = EventBus()
    bus.QUEUE_SIZE = 2  # Small for testing
    queue = await bus.subscribe("test-sub")
    # Need to recreate queue with smaller size since subscribe already created one
    async with bus._lock:
        bus._subscribers["test-sub"] = asyncio.Queue(maxsize=2)
        queue = bus._subscribers["test-sub"]
    for i in range(3):
        await bus.publish(
            Event(subsystem=Subsystem.MEMORY, event_type=f"event-{i}", data={})
        )
    # Queue should have events 1 and 2 (event 0 dropped)
    e1 = queue.get_nowait()
    e2 = queue.get_nowait()
    assert e1.event_type == "event-1"
    assert e2.event_type == "event-2"
    assert bus.total_dropped_events == 1


@pytest.mark.asyncio
async def test_empty_bus_publish_is_noop():
    bus = EventBus()
    event = Event(subsystem=Subsystem.MEMORY, event_type="created", data={})
    await bus.publish(event)  # Should not raise


@pytest.mark.asyncio
async def test_subscriber_count():
    bus = EventBus()
    assert bus.subscriber_count == 0
    await bus.subscribe("sub-1")
    assert bus.subscriber_count == 1
    await bus.subscribe("sub-2")
    assert bus.subscriber_count == 2
    await bus.unsubscribe("sub-1")
    assert bus.subscriber_count == 1


@pytest.mark.asyncio
async def test_event_has_timestamp():
    bus = EventBus()
    queue = await bus.subscribe("test-sub")
    event = Event(subsystem=Subsystem.MEMORY, event_type="created", data={})
    await bus.publish(event)
    received = queue.get_nowait()
    assert received.timestamp  # Should be auto-set
    assert "T" in received.timestamp  # ISO format


@pytest.mark.asyncio
async def test_event_preserves_namespace_and_session_id():
    bus = EventBus()
    queue = await bus.subscribe("test-sub")
    event = Event(
        subsystem=Subsystem.MEMORY,
        event_type="created",
        data={},
        namespace="test-project",
        session_id="sess-123",
    )
    await bus.publish(event)
    received = queue.get_nowait()
    assert received.namespace == "test-project"
    assert received.session_id == "sess-123"


@pytest.mark.asyncio
async def test_subsystem_values():
    """Verify all subsystem enum values are strings."""
    assert Subsystem.MEMORY.value == "memory"
    assert Subsystem.SESSION.value == "session"
    assert Subsystem.CONFIG.value == "config"
    assert Subsystem.FRACTAL.value == "fractal"
    assert Subsystem.EXPERIMENT.value == "experiment"
    assert Subsystem.FORGE.value == "forge"


@pytest.mark.asyncio
async def test_singleton_event_bus_exists():
    """The module-level singleton should be an EventBus instance."""
    assert isinstance(event_bus, EventBus)


@pytest.mark.asyncio
async def test_publish_sync_from_thread():
    """Test publish_sync() thread-safe wrapper for sync MCP handlers."""
    from spellbook.admin.events import publish_sync

    bus = EventBus()
    queue = await bus.subscribe("test-sub")
    loop = asyncio.get_event_loop()
    event = Event(subsystem=Subsystem.CONFIG, event_type="updated", data={"key": "x"})

    # Simulate calling from a sync thread
    result_holder = []

    def sync_call():
        try:
            publish_sync(event, bus=bus, loop=loop)
            result_holder.append("ok")
        except Exception as e:
            result_holder.append(f"error: {e}")

    thread = threading.Thread(target=sync_call)
    thread.start()
    thread.join(timeout=5)

    # Give the event loop a moment to process
    await asyncio.sleep(0.1)

    assert result_holder == ["ok"]
    assert not queue.empty()
    received = queue.get_nowait()
    assert received.event_type == "updated"


@pytest.mark.asyncio
async def test_unsubscribe_nonexistent_is_noop():
    bus = EventBus()
    await bus.unsubscribe("nonexistent")  # Should not raise


@pytest.mark.asyncio
async def test_duplicate_subscribe_replaces_queue():
    bus = EventBus()
    q1 = await bus.subscribe("sub-1")
    q2 = await bus.subscribe("sub-1")
    assert bus.subscriber_count == 1
    # Publishing should go to q2 (the replacement)
    await bus.publish(
        Event(subsystem=Subsystem.MEMORY, event_type="test", data={})
    )
    assert not q2.empty()
