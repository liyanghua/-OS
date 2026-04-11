"""Event Bus：对象级事件广播，支持 SSE 订阅。"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ObjectEvent(BaseModel):
    """对象变更事件。"""
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    event_type: str = ""
    opportunity_id: str = ""
    object_type: str = ""
    object_id: str = ""
    agent_role: str = ""
    agent_name: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EventBus:
    """进程内事件总线，支持按 opportunity_id 订阅。"""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._history: dict[str, list[ObjectEvent]] = {}
        self._max_history = 50

    def subscribe(self, opportunity_id: str) -> asyncio.Queue:
        """Subscribe to events for an opportunity. Returns an asyncio.Queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.setdefault(opportunity_id, []).append(q)
        return q

    def unsubscribe(self, opportunity_id: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(opportunity_id, [])
        if q in subs:
            subs.remove(q)
        if not subs:
            self._subscribers.pop(opportunity_id, None)

    async def publish(self, event: ObjectEvent) -> None:
        """Publish event to all subscribers of the opportunity."""
        oid = event.opportunity_id
        history = self._history.setdefault(oid, [])
        history.append(event)
        if len(history) > self._max_history:
            self._history[oid] = history[-self._max_history:]

        for q in self._subscribers.get(oid, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Event queue full for %s, dropping event %s", oid, event.event_id)

    def publish_sync(self, event: ObjectEvent) -> None:
        """Synchronous publish — works from any thread (main or executor)."""
        oid = event.opportunity_id
        history = self._history.setdefault(oid, [])
        history.append(event)
        if len(history) > self._max_history:
            self._history[oid] = history[-self._max_history:]

        if not self._subscribers.get(oid):
            return

        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._enqueue_nowait, oid, event)
        except RuntimeError:
            self._enqueue_nowait(oid, event)

    def _enqueue_nowait(self, oid: str, event: ObjectEvent) -> None:
        for q in self._subscribers.get(oid, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Event queue full for %s, dropping event %s", oid, event.event_id)

    def get_history(self, opportunity_id: str, since: float = 0) -> list[ObjectEvent]:
        """Get event history, optionally filtered by timestamp."""
        events = self._history.get(opportunity_id, [])
        if since > 0:
            cutoff = datetime.fromtimestamp(since, tz=UTC)
            return [e for e in events if e.timestamp >= cutoff]
        return list(events)

    def clear(self, opportunity_id: str | None = None) -> None:
        if opportunity_id:
            self._subscribers.pop(opportunity_id, None)
            self._history.pop(opportunity_id, None)
        else:
            self._subscribers.clear()
            self._history.clear()


# Singleton
event_bus = EventBus()


def emit_object_updated(
    opportunity_id: str,
    object_type: str,
    object_id: str = "",
    agent_role: str = "",
    agent_name: str = "",
    **extra: Any,
) -> None:
    """Convenience function to emit an object_updated event."""
    event_bus.publish_sync(ObjectEvent(
        event_type="object_updated",
        opportunity_id=opportunity_id,
        object_type=object_type,
        object_id=object_id,
        agent_role=agent_role,
        agent_name=agent_name,
        payload=extra,
    ))
