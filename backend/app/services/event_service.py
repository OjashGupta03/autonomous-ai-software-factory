"""
Event log + pub/sub fan-out (docs/22 in the brief -> docs/18-observability.md
and docs/16-frontend.md).

Every event the frontend can render live is written to `project_events`
first (durable, replayable for a client that connects late) and then
published on a Redis channel for low-latency fan-out to any SSE
connections currently open for that project. If Redis is briefly
unavailable, the DB write still succeeds and the event is only "late"
(the next poll/refresh will pick it up) rather than lost - the durable
log is authoritative, Redis is a latency optimization on top of it.
"""
from __future__ import annotations

import json
import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ProjectEventType
from app.models.event import ProjectEvent


def channel_for_project(project_id: str) -> str:
    return f"factory:events:{project_id}"


async def publish_event(
    db: AsyncSession,
    redis: Redis | None,
    project_id: uuid.UUID,
    event_type: ProjectEventType | str,
    payload: dict,
) -> ProjectEvent:
    type_value = event_type.value if isinstance(event_type, ProjectEventType) else event_type
    event = ProjectEvent(project_id=project_id, event_type=type_value, payload=payload)
    db.add(event)
    await db.commit()
    await db.refresh(event)

    if redis is not None:
        message = json.dumps(
            {
                "id": str(event.id),
                "project_id": str(project_id),
                "event_type": type_value,
                "payload": payload,
                "created_at": event.created_at.isoformat(),
            }
        )
        try:
            await redis.publish(channel_for_project(str(project_id)), message)
        except Exception:
            # Fan-out is best-effort; the durable row above already
            # succeeded, so a Redis hiccup must never fail the request
            # or lose the event, only delay a live client's view of it.
            pass

    return event


async def recent_events(db: AsyncSession, project_id: uuid.UUID, limit: int = 100) -> list[ProjectEvent]:
    from sqlalchemy import select

    result = await db.execute(
        select(ProjectEvent)
        .where(ProjectEvent.project_id == project_id)
        .order_by(ProjectEvent.created_at.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))
