"""SSE Handler：Server-Sent Events 端点实现。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from starlette.requests import Request
from starlette.responses import StreamingResponse

from apps.content_planning.gateway.event_bus import EventBus, ObjectEvent, event_bus

logger = logging.getLogger(__name__)


async def _event_generator(
    opportunity_id: str,
    bus: EventBus,
    request: Request,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for a specific opportunity."""
    q = bus.subscribe(opportunity_id)
    try:
        history = bus.get_history(opportunity_id)
        for evt in history[-20:]:
            yield _format_sse(evt)

        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(q.get(), timeout=15.0)
                yield _format_sse(event)
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
    finally:
        bus.unsubscribe(opportunity_id, q)


def _format_sse(event: ObjectEvent) -> str:
    """Format an ObjectEvent as an SSE message.

    Only the payload dict is sent as data so that frontend consumers
    can access fields (slot_id, status, provider, ...) at the top level
    without unwrapping an ObjectEvent wrapper.
    """
    data = event.payload
    lines = [
        f"id: {event.event_id}",
        f"event: {event.event_type}",
        f"data: {json.dumps(data, ensure_ascii=False)}",
        "",
        "",
    ]
    return "\n".join(lines)


async def sse_stream(request: Request, opportunity_id: str, bus: EventBus | None = None) -> StreamingResponse:
    """Create an SSE streaming response for the given opportunity."""
    _bus = bus or event_bus
    return StreamingResponse(
        _event_generator(opportunity_id, _bus, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
