import asyncio
import time
import pytest
from fastapi.testclient import TestClient

from services.event_bus import (
    EventBus,
    SSEMessage,
    get_event_bus,
    reset_event_bus,
    sse_event_generator,
)
from services.watcher_service import (
    VaultChangeEvent,
    VaultWatcherService,
    reset_vault_watcher,
)


@pytest.fixture(autouse=True)
def clean_singletons():
    reset_event_bus()
    reset_vault_watcher()
    yield
    reset_event_bus()
    reset_vault_watcher()


def test_sse_message_format_standard():
    """Verify SSEMessage formats W3C compliant SSE lines with id, event, and data."""
    msg = SSEMessage(
        id="42",
        event="vault_change",
        data={"action": "modified", "path": "Journal/2026-10-02.md"},
        retry=5000,
    )
    formatted = msg.format()
    lines = formatted.split("\n")
    assert "id: 42" in lines
    assert "event: vault_change" in lines
    assert "retry: 5000" in lines
    assert 'data: {"action": "modified", "path": "Journal/2026-10-02.md"}' in lines
    assert formatted.endswith("\n\n")


def test_sse_message_format_comment():
    """Verify SSEMessage comment formats as : <comment> without event/data fields."""
    msg = SSEMessage(comment="ping")
    assert msg.format() == ": ping\n\n"


def test_sse_message_format_multiline_data():
    """Verify multiline string data is split into multiple data: lines per SSE specification."""
    msg = SSEMessage(event="log", data="line1\nline2\nline3")
    formatted = msg.format()
    expected = "event: log\ndata: line1\ndata: line2\ndata: line3\n\n"
    assert formatted == expected


def test_sse_message_format_empty_data():
    """Verify empty/None data generates data: line."""
    msg = SSEMessage(id="1")
    assert msg.format() == "id: 1\ndata: \n\n"


@pytest.mark.anyio
async def test_event_bus_subscription_and_publish():
    """Verify multiple subscribers receive published messages concurrently."""
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    assert bus.subscriber_count == 2

    bus.publish_event(event="test_event", data={"message": "hello"})

    msg1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    msg2 = await asyncio.wait_for(q2.get(), timeout=1.0)

    assert msg1.id == "1"
    assert msg1.event == "test_event"
    assert msg1.data == {"message": "hello"}
    assert msg2.id == "1"

    # Monotonic ID increment
    bus.publish_event(event="next_event", data="second")
    msg1_second = await asyncio.wait_for(q1.get(), timeout=1.0)
    assert msg1_second.id == "2"

    bus.unsubscribe(q1)
    assert bus.subscriber_count == 1
    bus.unsubscribe(q2)
    assert bus.subscriber_count == 0


@pytest.mark.anyio
async def test_event_bus_queue_overflow_policy():
    """Verify full queues drop oldest messages to avoid blocking other subscribers."""
    bus = EventBus()
    q = bus.subscribe(maxsize=2)

    # Publish 3 events into queue with maxsize=2
    bus.publish_event(event="e1", data="first")
    bus.publish_event(event="e2", data="second")
    bus.publish_event(event="e3", data="third")

    # Queue should contain e2 and e3 (e1 was evicted)
    item1 = q.get_nowait()
    assert item1.data == "second"
    item2 = q.get_nowait()
    assert item2.data == "third"
    assert q.empty()

    bus.unsubscribe(q)


@pytest.mark.anyio
async def test_event_bus_watcher_bridge(tmp_path):
    """Verify attach_watcher bridges VaultChangeEvent into vault_change SSE events."""
    bus = EventBus()
    watcher = VaultWatcherService(root_path=tmp_path)
    detach = bus.attach_watcher(watcher)

    q = bus.subscribe()

    evt = VaultChangeEvent(
        type="journal",
        path="Journal/2026/10/2026-10-02.md",
        timestamp=time.time(),
        action="created",
    )
    watcher.emit(evt)

    received = await asyncio.wait_for(q.get(), timeout=1.0)
    assert received.event == "vault_change"
    assert received.data["type"] == "journal"
    assert received.data["path"] == "Journal/2026/10/2026-10-02.md"
    assert received.data["action"] == "created"

    detach()
    # Emitting after detach should not produce new SSE events
    watcher.emit(evt)
    await asyncio.sleep(0.05)
    assert q.empty()

    bus.unsubscribe(q)


@pytest.mark.anyio
async def test_sse_event_generator_keepalive():
    """Verify sse_event_generator emits : ping comments on idle timeouts."""
    class FakeRequest:
        def __init__(self):
            self.disconnected = False

        async def is_disconnected(self) -> bool:
            return self.disconnected

    bus = EventBus()
    req = FakeRequest()

    gen = sse_event_generator(req, bus, keepalive_interval=0.1)
    # Generator starts and subscribes
    assert bus.subscriber_count == 0

    first_item = await anext(gen)
    assert bus.subscriber_count == 1
    assert first_item == ": connected\n\n"

    # Second item is keepalive ping comment after timeout
    second_item = await anext(gen)
    assert second_item == ": ping\n\n"

    # Publish an event to ensure generator yields message
    bus.publish_event(event="tick", data={"status": "ok"})
    third_item = await anext(gen)
    assert "event: tick" in third_item
    assert 'data: {"status": "ok"}' in third_item

    # Disconnect / client cancellation
    await gen.aclose()

    # Clean unsubscription without memory leak
    assert bus.subscriber_count == 0


def test_api_events_stream_testclient_keepalive(monkeypatch):
    """Verify GET /api/events/stream connects via TestClient and emits initial connection & keepalive ping."""
    from main import app

    monkeypatch.setenv("NAVIS_SSE_KEEPALIVE_INTERVAL", "0.05")

    client = TestClient(app)
    bus = get_event_bus()

    # Limit to 2 items (1: initial : connected, 2: : ping keepalive)
    response = client.get("/api/events/stream?limit=2")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert response.headers.get("cache-control") == "no-cache"

    body = response.text
    assert ": connected" in body
    assert ": ping" in body

    # Clean unsubscription verified
    assert bus.subscriber_count == 0


def test_api_events_stream_testclient_broadcast(monkeypatch):
    """Verify GET /api/events/stream receives formatted SSE broadcast via TestClient."""
    from main import app

    monkeypatch.setenv("NAVIS_SSE_KEEPALIVE_INTERVAL", "1.0")

    client = TestClient(app)
    bus = get_event_bus()

    def publish_when_ready():
        for _ in range(100):
            if bus.subscriber_count > 0:
                break
            time.sleep(0.01)
        bus.publish_event(event="vault_change", data={"action": "created", "path": "Journal/today.md"})

    import threading
    t = threading.Thread(target=publish_when_ready)
    t.start()

    response = client.get("/api/events/stream?limit=2")
    t.join()

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    body = response.text
    assert ": connected" in body
    assert "event: vault_change" in body
    assert 'data: {"action": "created", "path": "Journal/today.md"}' in body
    assert "id: 1" in body

    # Clean unsubscription verified
    assert bus.subscriber_count == 0


@pytest.mark.anyio
async def test_concurrent_subscriptions_lifecycle():
    """Verify multiple concurrent client subscriptions manage queues independently without leaks."""
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    q3 = bus.subscribe()
    assert bus.subscriber_count == 3

    bus.publish_event(event="broadcast", data={"batch": 1})

    m1 = await q1.get()
    m2 = await q2.get()
    m3 = await q3.get()

    assert m1.data == {"batch": 1}
    assert m2.data == {"batch": 1}
    assert m3.data == {"batch": 1}

    bus.unsubscribe(q2)
    assert bus.subscriber_count == 2

    bus.publish_event(event="broadcast", data={"batch": 2})
    m1_2 = await q1.get()
    m3_2 = await q3.get()
    assert m1_2.data == {"batch": 2}
    assert m3_2.data == {"batch": 2}
    assert q2.empty()

    bus.unsubscribe(q1)
    bus.unsubscribe(q3)
    assert bus.subscriber_count == 0
