"""
Server-Sent Events stream for live project updates (docs/22 in the brief
-> docs/16-frontend.md "Live Agent Activity").

Why SSE over WebSockets: every event in this system flows server -> client
only (the frontend never needs to push data back over this channel -
approvals, retries etc. are ordinary POST requests). SSE is plain HTTP,
so it works through normal proxies/load balancers without upgrade
handling, reconnects natively in the browser (EventSource), and is
simpler to reason about than a bidirectional socket for a use case that
is not bidirectional. See docs/23-design-decisions.md.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.event_service import channel_for_project, recent_events

_HEARTBEAT_SECONDS = 20


async def project_event_stream(
    db: AsyncSession, redis: Redis | None, project_id: uuid.UUID
) -> AsyncGenerator[str, None]:
    # 1. Replay recent history first, so a client that connects after the
    #    run has already started sees how it got here, not just what
    #    happens from now on.
    for event in await recent_events(db, project_id, limit=100):
        yield _format_sse(
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "payload": event.payload,
                "created_at": event.created_at.isoformat(),
            }
        )

    if redis is None:
        # No Redis configured - the client still got the replay above,
        # it just will not receive further live updates. Callers should
        # prefer polling the REST endpoints in this mode.
        return

    pubsub = redis.pubsub()
    await pubsub.subscribe(channel_for_project(str(project_id)))
    try:
        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=_HEARTBEAT_SECONDS),
                    timeout=_HEARTBEAT_SECONDS + 5,
                )
            except asyncio.TimeoutError:
                message = None

            if message is None:
                yield ": heartbeat\n\n"  # SSE comment line - keeps proxies from closing an idle connection
                continue

            data = message["data"]
            text = data.decode() if isinstance(data, bytes) else data
            yield f"data: {text}\n\n"
    finally:
        await pubsub.unsubscribe(channel_for_project(str(project_id)))
        await pubsub.aclose()


def _format_sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"
