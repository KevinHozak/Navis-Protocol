import asyncio
import time
import pytest
from watchfiles import Change

from services.watcher_service import (
    VaultChangeEvent,
    VaultWatcherFilter,
    VaultWatcherService,
    get_vault_watcher,
    reset_vault_watcher,
)


@pytest.fixture(autouse=True)
def clean_watcher_singleton():
    reset_vault_watcher()
    yield
    reset_vault_watcher()


def test_vault_change_event_model():
    """Verify VaultChangeEvent generates typed event payloads with type, path, timestamp, action."""
    now = time.time()
    evt = VaultChangeEvent(
        type="journal",
        path="Journal/2026/10/2026-10-02.md",
        timestamp=now,
        action="created",
        full_path="C:/Vault/Journal/2026/10/2026-10-02.md",
    )
    assert evt.type == "journal"
    assert evt.path == "Journal/2026/10/2026-10-02.md"
    assert evt.timestamp == now
    assert evt.action == "created"
    assert evt.full_path == "C:/Vault/Journal/2026/10/2026-10-02.md"

    dump = evt.model_dump()
    assert dump["type"] == "journal"
    assert dump["action"] == "created"


def test_vault_watcher_filter_supervision(tmp_path):
    """Verify watcher filter supervises Journal/, Bridge/, and Keeper/ while ignoring others."""
    root = tmp_path
    (root / "Journal").mkdir()
    (root / "Bridge").mkdir()
    (root / "Keeper").mkdir()
    (root / "Operations").mkdir()

    v_filter = VaultWatcherFilter(root, {"Journal", "Bridge", "Keeper"})

    # Supervised directories and files within them
    assert v_filter(Change.added, str(root / "Journal")) is True
    assert v_filter(Change.added, str(root / "Journal" / "2026-10-02.md")) is True
    assert v_filter(Change.modified, str(root / "Bridge" / "CompanionStats.json")) is True
    assert v_filter(Change.deleted, str(root / "Keeper" / "active_keeper.md")) is True

    # Unsupervised directories and files
    assert v_filter(Change.added, str(root / "Operations")) is False
    assert v_filter(Change.added, str(root / "Operations" / "task.md")) is False
    assert v_filter(Change.modified, str(root / "Library" / "book.md")) is False

    # Temporary, lock, and hidden files
    assert v_filter(Change.added, str(root / "Journal" / ".hidden.md")) is False
    assert v_filter(Change.modified, str(root / "Journal" / "notes.tmp")) is False
    assert v_filter(Change.modified, str(root / "Bridge" / "~$stats.json")) is False
    assert v_filter(Change.modified, str(root / "Keeper" / "file.swp")) is False
    assert v_filter(Change.added, str(root / "Journal" / ".DS_Store")) is False


@pytest.mark.anyio
async def test_watcher_debouncing_coalesces_rapid_writes(tmp_path):
    """Verify debounce timer coalesces multi-write disk flushes into a single settled event."""
    (tmp_path / "Journal").mkdir(parents=True)
    target_file = tmp_path / "Journal" / "daily_entry.md"
    target_file.write_text("initial content", encoding="utf-8")

    watcher = VaultWatcherService(
        root_path=tmp_path,
        supervised_dirs={"Journal"},
        debounce_ms=150,
    )
    events_received = []
    event_arrived = asyncio.Event()

    def on_event(evt: VaultChangeEvent):
        events_received.append(evt)
        event_arrived.set()

    watcher.add_listener(on_event)
    await watcher.start()

    try:
        # Give watcher loop a moment to initialize
        await asyncio.sleep(0.1)

        # Perform 5 rapid writes in quick succession (under debounce threshold)
        for i in range(5):
            target_file.write_text(f"rapid update {i}", encoding="utf-8")
            await asyncio.sleep(0.01)

        # Wait for debounce window to settle and event to be emitted
        await asyncio.wait_for(event_arrived.wait(), timeout=3.0)

        # Allow extra time to confirm no duplicate bursts follow
        await asyncio.sleep(0.3)

        assert len(events_received) == 1
        assert events_received[0].type == "journal"
        assert events_received[0].action in ("modified", "created")
        assert "daily_entry.md" in events_received[0].path
    finally:
        await watcher.stop()


@pytest.mark.anyio
async def test_watcher_event_actions_and_types(tmp_path):
    """Verify creation, modification, and deletion generate correct typed event payloads."""
    (tmp_path / "Bridge").mkdir(parents=True)
    stats_file = tmp_path / "Bridge" / "CompanionStats.json"

    watcher = VaultWatcherService(
        root_path=tmp_path,
        supervised_dirs={"Bridge"},
        debounce_ms=100,
    )
    queue = watcher.subscribe()
    await watcher.start()

    try:
        await asyncio.sleep(0.1)

        # 1. Created action
        stats_file.write_text('{"level": 1}', encoding="utf-8")
        evt_create = await asyncio.wait_for(queue.get(), timeout=3.0)
        assert evt_create.type == "bridge"
        assert evt_create.action == "created"
        assert evt_create.path == "Bridge/CompanionStats.json"

        # 2. Modified action
        stats_file.write_text('{"level": 2}', encoding="utf-8")
        evt_mod = await asyncio.wait_for(queue.get(), timeout=3.0)
        assert evt_mod.type == "bridge"
        assert evt_mod.action == "modified"

        # 3. Deleted action
        stats_file.unlink()
        evt_del = await asyncio.wait_for(queue.get(), timeout=3.0)
        assert evt_del.type == "bridge"
        assert evt_del.action == "deleted"
    finally:
        watcher.unsubscribe(queue)
        await watcher.stop()


@pytest.mark.anyio
async def test_watcher_event_filtering_ignores_unsupervised(tmp_path):
    """Verify modifications outside supervised directories or on temp files are not emitted."""
    (tmp_path / "Journal").mkdir(parents=True)
    (tmp_path / "Operations").mkdir(parents=True)

    watcher = VaultWatcherService(
        root_path=tmp_path,
        supervised_dirs={"Journal"},
        debounce_ms=100,
    )
    queue = watcher.subscribe()
    await watcher.start()

    try:
        await asyncio.sleep(0.1)

        # Unsupervised directory write
        (tmp_path / "Operations" / "unsupervised.md").write_text("ignore me", encoding="utf-8")
        # Temporary file inside supervised directory
        (tmp_path / "Journal" / ".temp_lock.tmp").write_text("lock", encoding="utf-8")

        await asyncio.sleep(0.3)
        assert queue.empty()

        # Legitimate file inside supervised directory
        (tmp_path / "Journal" / "valid.md").write_text("valid entry", encoding="utf-8")
        evt = await asyncio.wait_for(queue.get(), timeout=3.0)
        assert evt.type == "journal"
        assert evt.path == "Journal/valid.md"
        assert queue.empty()
    finally:
        watcher.unsubscribe(queue)
        await watcher.stop()


@pytest.mark.anyio
async def test_subscription_and_queue_listeners(tmp_path):
    """Verify sync callbacks, async callbacks, and queue subscribers all receive events."""
    (tmp_path / "Keeper").mkdir(parents=True)
    keeper_file = tmp_path / "Keeper" / "active.md"

    watcher = VaultWatcherService(
        root_path=tmp_path,
        supervised_dirs={"Keeper"},
        debounce_ms=100,
    )

    sync_results = []
    async_results = []

    def sync_listener(evt: VaultChangeEvent):
        sync_results.append(evt)

    async def async_listener(evt: VaultChangeEvent):
        async_results.append(evt)

    unsub_sync = watcher.add_listener(sync_listener)
    unsub_async = watcher.add_listener(async_listener)
    queue = watcher.subscribe()

    await watcher.start()
    try:
        await asyncio.sleep(0.1)
        keeper_file.write_text("keeper updated", encoding="utf-8")

        evt = await asyncio.wait_for(queue.get(), timeout=3.0)
        assert evt.type == "keeper"
        # Give async task callbacks a moment to resolve
        await asyncio.sleep(0.1)

        assert len(sync_results) == 1
        assert len(async_results) == 1
        assert sync_results[0].type == "keeper"
        assert async_results[0].type == "keeper"

        # Test unsubscription
        unsub_sync()
        unsub_async()
        watcher.unsubscribe(queue)

        keeper_file.write_text("second update", encoding="utf-8")
        await asyncio.sleep(0.3)

        assert len(sync_results) == 1
        assert len(async_results) == 1
        assert queue.empty()
    finally:
        await watcher.stop()


@pytest.mark.anyio
async def test_watcher_clean_shutdown(tmp_path):
    """Verify clean shutdown releases background task and resets running state."""
    watcher = VaultWatcherService(root_path=tmp_path)
    assert not watcher.is_running

    task = await watcher.start()
    assert watcher.is_running
    assert task is not None
    assert not task.done()

    await watcher.stop()
    assert not watcher.is_running
    assert task.done()


@pytest.mark.anyio
async def test_missing_vault_root_handling(tmp_path):
    """Verify watcher gracefully handles a non-existent vault root path without crashing."""
    missing_dir = tmp_path / "does_not_exist_at_all"
    watcher = VaultWatcherService(root_path=missing_dir)

    task = await watcher.start()
    assert watcher.is_running
    # Ensure it doesn't crash
    await asyncio.sleep(0.2)
    assert not task.done()

    await watcher.stop()
    assert not watcher.is_running
    assert task.done()


@pytest.mark.anyio
async def test_fastapi_lifespan_integration(monkeypatch, tmp_path):
    """Verify FastAPI lifespan starts and cleanly terminates the watcher service."""
    from main import app, lifespan

    # Point NAVIS_ROOT to tmp_path
    monkeypatch.setenv("NAVIS_ROOT", str(tmp_path))
    monkeypatch.setattr("main.NAVIS_ROOT", str(tmp_path))

    # Run lifespan context manager
    async with lifespan(app):
        watcher = get_vault_watcher(str(tmp_path))
        assert watcher.is_running

    assert not watcher.is_running
