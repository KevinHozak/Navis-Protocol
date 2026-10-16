"""
Event Bus & Server-Sent Events (SSE) Dispatcher (Reactive-P2).
Provides an asynchronous in-memory event bus managing multi-client SSE subscriptions,
formatting W3C SSE payloads, broadcasting keepalive pings, and bridging
VaultWatcherService filesystem events to connected clients without memory leaks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Set

from fastapi import Request
from pydantic import BaseModel, Field

from services.watcher_service import VaultChangeEvent, VaultWatcherService

logger = logging.getLogger("navis.event_bus")

DEFAULT_KEEPALIVE_INTERVAL = 15.0  # seconds


class SSEMessage(BaseModel):
    """Model representing an SSE message compliant with the W3C EventSource spec."""

    id: Optional[str] = Field(default=None, description="Event ID for client reconnection tracking.")
    event: Optional[str] = Field(default=None, description="Event type name (e.g. 'vault_change').")
    data: Optional[Any] = Field(default=None, description="Payload data (dict, list, string, or primitive).")
    retry: Optional[int] = Field(default=None, description="Reconnection time in milliseconds.")
    comment: Optional[str] = Field(default=None, description="Comment line (e.g. 'ping' for keepalive).")

    def format(self) -> str:
        """Format the message into standard SSE wire representation."""
        if self.comment is not None:
            return f": {self.comment}\n\n"

        lines: List[str] = []
        if self.id is not None:
            lines.append(f"id: {self.id}")
        if self.event is not None:
            lines.append(f"event: {self.event}")
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")

        payload_str: str = ""
        if self.data is not None:
            if isinstance(self.data, (dict, list)):
                payload_str = json.dumps(self.data)
            elif isinstance(self.data, BaseModel):
                payload_str = self.data.model_dump_json()
            else:
                payload_str = str(self.data)

            # Handle multiline data according to W3C SSE specification
            split_lines = payload_str.splitlines()
            if not split_lines:
                lines.append("data: ")
            else:
                for line in split_lines:
                    lines.append(f"data: {line}")
        else:
            lines.append("data: ")

        return "\n".join(lines) + "\n\n"


class EventBus:
    """Centralized asynchronous pub/sub event bus for SSE streaming."""

    def __init__(self, default_keepalive_interval: float = DEFAULT_KEEPALIVE_INTERVAL):
        self._subscribers: Dict[asyncio.Queue[SSEMessage], Optional[asyncio.AbstractEventLoop]] = {}
        self._event_counter: int = 0
        self._watcher_unsubscribe: Optional[Callable[[], None]] = None
        self.default_keepalive_interval = default_keepalive_interval

    @property
    def subscriber_count(self) -> int:
        """Return the number of active subscriber queues."""
        return len(self._subscribers)

    def _next_id(self) -> str:
        self._event_counter += 1
        return str(self._event_counter)

    def subscribe(self, maxsize: int = 256) -> asyncio.Queue[SSEMessage]:
        """Register a new client subscription queue."""
        queue: asyncio.Queue[SSEMessage] = asyncio.Queue(maxsize=maxsize)
        loop: Optional[asyncio.AbstractEventLoop] = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        self._subscribers[queue] = loop
        logger.debug("New subscriber connected. Total subscribers: %d", len(self._subscribers))
        return queue

    def unsubscribe(self, queue: asyncio.Queue[SSEMessage]) -> None:
        """Unregister a client subscription queue."""
        self._subscribers.pop(queue, None)
        logger.debug("Subscriber disconnected. Total subscribers: %d", len(self._subscribers))

    def _deliver_to_queue(self, q: asyncio.Queue[SSEMessage], message: SSEMessage) -> None:
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            try:
                _ = q.get_nowait()
                q.put_nowait(message)
            except Exception:
                pass

    def publish(self, message: SSEMessage) -> None:
        """Publish an SSEMessage to all connected subscribers."""
        dead_queues: Set[asyncio.Queue[SSEMessage]] = set()
        current_loop: Optional[asyncio.AbstractEventLoop] = None
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        for q, target_loop in list(self._subscribers.items()):
            try:
                if target_loop and target_loop.is_running() and target_loop is not current_loop:
                    target_loop.call_soon_threadsafe(self._deliver_to_queue, q, message)
                else:
                    self._deliver_to_queue(q, message)
            except Exception:
                dead_queues.add(q)

        for q in dead_queues:
            self._subscribers.pop(q, None)

    def publish_event(
        self,
        event: str,
        data: Any,
        id: Optional[str] = None,
        retry: Optional[int] = None,
    ) -> SSEMessage:
        """Helper to create and broadcast an SSE message with an automatically incremented ID."""
        msg_id = id if id is not None else self._next_id()
        msg = SSEMessage(id=msg_id, event=event, data=data, retry=retry)
        self.publish(msg)
        return msg

    def attach_watcher(self, watcher: VaultWatcherService) -> Callable[[], None]:
        """Attach a VaultWatcherService to automatically bridge filesystem change events."""
        self.detach_watcher()

        def _on_vault_change(event: VaultChangeEvent):
            self.publish_event(
                event="vault_change",
                data=event.model_dump(),
            )

        self._watcher_unsubscribe = watcher.add_listener(_on_vault_change)
        return self.detach_watcher

    def detach_watcher(self) -> None:
        """Detach any currently connected VaultWatcherService."""
        if self._watcher_unsubscribe:
            try:
                self._watcher_unsubscribe()
            except Exception:
                pass
            self._watcher_unsubscribe = None

    def clear(self) -> None:
        """Clear all subscribers and reset internal state."""
        self.detach_watcher()
        self._subscribers.clear()
        self._event_counter = 0


async def sse_event_generator(
    request: Optional[Request],
    event_bus: EventBus,
    keepalive_interval: Optional[float] = None,
    limit: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE messages and keepalive pings for a streaming response."""
    interval = (
        keepalive_interval
        if keepalive_interval is not None
        else float(os.getenv("NAVIS_SSE_KEEPALIVE_INTERVAL", str(event_bus.default_keepalive_interval)))
    )
    queue = event_bus.subscribe()
    yielded_count = 0
    try:
        # Emit initial SSE comment so HTTP headers are immediately committed to client
        yield ": connected\n\n"
        yielded_count += 1
        if limit is not None and yielded_count >= limit:
            return

        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=interval)
                yield msg.format()
                yielded_count += 1
            except asyncio.TimeoutError:
                # Send SSE comment keepalive ping
                yield ": ping\n\n"
                yielded_count += 1

            if limit is not None and yielded_count >= limit:
                break
    except (asyncio.CancelledError, GeneratorExit):
        pass
    finally:
        event_bus.unsubscribe(queue)


# Global Singleton Management
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Retrieve or initialize the global EventBus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global EventBus singleton (useful for test isolation)."""
    global _event_bus
    if _event_bus is not None:
        _event_bus.clear()
    _event_bus = None
