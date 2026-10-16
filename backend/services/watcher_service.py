"""
Watcher Service Daemon & State Event Emitter (Reactive-P1).
Supervises key Vault directories (Journal/, Bridge/, Keeper/) asynchronously
with debounced coalescing and emits typed VaultChangeEvent payloads.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Set, Union

from pydantic import BaseModel, Field
from watchfiles import Change, DefaultFilter, awatch

logger = logging.getLogger("navis.watcher")

DEFAULT_SUPERVISED_DIRS: Set[str] = {"Journal", "Bridge", "Keeper"}
DEFAULT_DEBOUNCE_MS: int = 250

CHANGE_ACTION_MAP: Dict[Change, Literal["created", "modified", "deleted"]] = {
    Change.added: "created",
    Change.modified: "modified",
    Change.deleted: "deleted",
}


class VaultChangeEvent(BaseModel):
    """Structured typed event payload emitted when vault files settle."""

    type: str = Field(description="Category or manifold of the file (e.g. 'journal', 'bridge', 'keeper').")
    path: str = Field(description="Normalized POSIX path relative to the Vault root.")
    timestamp: float = Field(default_factory=time.time, description="Epoch timestamp of the event settlement.")
    action: Literal["created", "modified", "deleted"] = Field(description="Filesystem action detected.")
    full_path: Optional[str] = Field(default=None, description="Absolute filesystem path on the host system.")


class VaultWatcherFilter:
    """Watchfiles filter that restricts supervision to designated Vault subdirectories

    and filters out temporary, lock, and cache files.
    """

    def __init__(self, root_path: Union[str, Path], supervised_dirs: Optional[Set[str]] = None):
        self.root_path = Path(root_path).resolve()
        dirs = supervised_dirs if supervised_dirs is not None else DEFAULT_SUPERVISED_DIRS
        self.supervised_dirs = {d.lower() for d in dirs}
        self._default_filter = DefaultFilter()

    def __call__(self, change: Change, path_str: str) -> bool:
        # Check standard default filter (skips .git, __pycache__, node_modules, etc.)
        if not self._default_filter(change, path_str):
            return False

        try:
            target = Path(path_str).resolve()
            rel = target.relative_to(self.root_path)
        except (ValueError, RuntimeError):
            return False

        parts = rel.parts
        # Root directory itself allows recursive traversal
        if not parts:
            return True

        # First segment must be one of the supervised directories
        if parts[0].lower() not in self.supervised_dirs:
            return False

        filename = parts[-1]
        # Ignore temporary, hidden, editor lock, and swap files
        if (
            filename.startswith(".")
            or filename.startswith("~$")
            or filename.endswith("~")
            or filename.endswith(".tmp")
            or filename.endswith(".crdownload")
            or filename.endswith(".swp")
            or filename.endswith(".swo")
            or filename == ".DS_Store"
        ):
            return False

        return True


class VaultWatcherService:
    """Asynchronous filesystem watcher daemon supervising Vault directories

    and emitting debounced, typed state events.
    """

    def __init__(
        self,
        root_path: Optional[Union[str, Path]] = None,
        supervised_dirs: Optional[Set[str]] = None,
        debounce_ms: int = DEFAULT_DEBOUNCE_MS,
        emit_directories: bool = False,
    ):
        raw_root = root_path or os.getenv("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
        self.root_path = Path(raw_root).resolve()
        self.supervised_dirs = set(supervised_dirs) if supervised_dirs is not None else set(DEFAULT_SUPERVISED_DIRS)
        self.debounce_ms = max(50, debounce_ms)
        self.emit_directories = emit_directories

        self._listeners: Set[Callable[[VaultChangeEvent], Any]] = set()
        self._queues: Set[asyncio.Queue[VaultChangeEvent]] = set()

        self._task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._is_running: bool = False
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._is_running

    def add_listener(self, callback: Callable[[VaultChangeEvent], Any]) -> Callable[[], None]:
        """Register a callback for vault change events.

        Returns an unregister callable.
        """
        self._listeners.add(callback)

        def unsubscribe():
            self.remove_listener(callback)

        return unsubscribe

    def remove_listener(self, callback: Callable[[VaultChangeEvent], Any]) -> None:
        """Unregister a callback."""
        self._listeners.discard(callback)

    def subscribe(self, maxsize: int = 256) -> asyncio.Queue[VaultChangeEvent]:
        """Create an asyncio.Queue subscription for consuming events (e.g.

        SSE streams).
        """
        q: asyncio.Queue[VaultChangeEvent] = asyncio.Queue(maxsize=maxsize)
        self._queues.add(q)
        return q

    def unsubscribe(self, queue: asyncio.Queue[VaultChangeEvent]) -> None:
        """Unregister an event subscription queue."""
        self._queues.discard(queue)

    def emit(self, event: VaultChangeEvent) -> None:
        """Dispatch a VaultChangeEvent to all registered callbacks and queues."""
        # Dispatch to queue subscribers
        dead_queues = set()
        for q in self._queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Discard oldest item to keep newest telemetry fresh
                try:
                    _ = q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    dead_queues.add(q)
            except Exception:
                dead_queues.add(q)

        for q in dead_queues:
            self._queues.discard(q)

        # Dispatch to callback listeners
        for listener in list(self._listeners):
            try:
                if inspect.iscoroutinefunction(listener):
                    asyncio.create_task(listener(event))
                else:
                    res = listener(event)
                    if inspect.isawaitable(res):
                        asyncio.create_task(res)
            except Exception as e:
                logger.error("Error executing vault watcher listener %s: %s", listener, e)

    def emit_many(self, events: List[VaultChangeEvent]) -> None:
        """Dispatch multiple events sequentially."""
        for event in events:
            self.emit(event)

    def _determine_event_type(self, rel_path: Path) -> str:
        """Determine event category manifold from path."""
        parts = rel_path.parts
        if parts:
            first = parts[0].lower()
            return first
        return "vault"

    def _create_event(self, change: Change, target_path: Path) -> Optional[VaultChangeEvent]:
        """Convert a watchfiles Change and target path to VaultChangeEvent."""
        try:
            rel = target_path.resolve().relative_to(self.root_path)
        except (ValueError, RuntimeError):
            return None

        # Filter out pure directory modifications if emit_directories is False
        if not self.emit_directories:
            try:
                if target_path.is_dir() and change == Change.modified:
                    return None
            except Exception:
                pass

        action = CHANGE_ACTION_MAP.get(change, "modified")
        event_type = self._determine_event_type(rel)

        return VaultChangeEvent(
            type=event_type,
            path=rel.as_posix(),
            timestamp=time.time(),
            action=action,
            full_path=str(target_path.resolve()),
        )

    async def start(self) -> Optional[asyncio.Task]:
        """Start the background filesystem watcher loop."""
        async with self._lock:
            if self._is_running:
                return self._task

            self._stop_event = asyncio.Event()
            self._is_running = True
            self._task = asyncio.create_task(self._run_loop(), name="navis_vault_watcher")
            logger.info("VaultWatcherService started monitoring %s (debounce: %sms)", self.root_path, self.debounce_ms)
            return self._task

    async def stop(self) -> None:
        """Cleanly terminate the watcher daemon and release handles."""
        async with self._lock:
            if not self._is_running:
                return

            self._is_running = False
            if self._stop_event:
                self._stop_event.set()

            if self._task:
                self._task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(self._task), timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                    pass
                self._task = None

            self._stop_event = None
            logger.info("VaultWatcherService cleanly stopped.")

    async def _run_loop(self) -> None:
        """Main watcher loop with path recovery and error boundary."""
        watch_filter = VaultWatcherFilter(self.root_path, self.supervised_dirs)

        while self._is_running and self._stop_event and not self._stop_event.is_set():
            if not self.root_path.exists():
                logger.warning(
                    "Vault root does not exist: %s. Watcher waiting for directory availability...", self.root_path
                )
                try:
                    await asyncio.sleep(5.0)
                except asyncio.CancelledError:
                    break
                continue

            try:
                async for changes in awatch(
                    self.root_path,
                    watch_filter=watch_filter,
                    debounce=self.debounce_ms,
                    step=50,
                    stop_event=self._stop_event,
                ):
                    if not self._is_running or (self._stop_event and self._stop_event.is_set()):
                        break

                    # Deduplicate and normalize changes within the settled debounce batch
                    path_changes: Dict[str, Change] = {}
                    for change, path_str in changes:
                        # Prioritize delete over others if present in batch, or take newest
                        path_changes[path_str] = change

                    events: List[VaultChangeEvent] = []
                    for path_str, change in path_changes.items():
                        evt = self._create_event(change, Path(path_str))
                        if evt:
                            events.append(evt)

                    if events:
                        self.emit_many(events)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._is_running:
                    break
                logger.warning("Vault watcher encountered an error in watchfiles loop: %s. Retrying in 2s...", e)
                try:
                    await asyncio.sleep(2.0)
                except asyncio.CancelledError:
                    break


# Global Singleton Management
_vault_watcher: Optional[VaultWatcherService] = None


def get_vault_watcher(
    root_path: Optional[Union[str, Path]] = None,
    supervised_dirs: Optional[Set[str]] = None,
    debounce_ms: int = DEFAULT_DEBOUNCE_MS,
) -> VaultWatcherService:
    """Retrieve or initialize the global VaultWatcherService singleton."""
    global _vault_watcher
    if _vault_watcher is None:
        _vault_watcher = VaultWatcherService(
            root_path=root_path,
            supervised_dirs=supervised_dirs,
            debounce_ms=debounce_ms,
        )
    return _vault_watcher


def reset_vault_watcher() -> None:
    """Reset the global singleton (for testing isolation)."""
    global _vault_watcher
    _vault_watcher = None
