from __future__ import annotations

import json
import uuid
from typing import Sequence

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ProjectEventType
from app.models.event import ProjectEvent


def channel_for_project(project_id: str | uuid.UUID) -> str:
    """Returns the Redis pub/sub channel name for a given project."""
    return f"project_events:{project_id}"


async def recent_events(db: AsyncSession, project_id: uuid.UUID, limit: int = 100) -> Sequence[ProjectEvent]:
    """Retrieves the most recent events for a project so late-connecting SSE clients
    can replay what they missed. Returns them in chronological order (oldest first)."""
    result = await db.execute(
        select(ProjectEvent)
        .where(ProjectEvent.project_id == project_id)
        .order_by(ProjectEvent.created_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    # Reverse so the oldest event of the batch comes first for correct playback
    return list(reversed(events))


async def publish_event(
    db: AsyncSession,
    redis: Redis | None,
    project_id: uuid.UUID,
    event_type: ProjectEventType | str,
    payload: dict,
) -> None:
    """Writes an event durably to Postgres (so it's available for replay and auditing),
    and if Redis is configured, publishes it to the project's pub/sub channel for live SSE."""
    
    event_type_str = event_type.value if hasattr(event_type, "value") else str(event_type)
        
    event = ProjectEvent(
        project_id=project_id,
        event_type=event_type_str,
        payload=payload,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    if redis is not None:
        message = {
            "id": str(event.id),
            "event_type": event.event_type,
            "payload": event.payload,
            "created_at": event.created_at.isoformat(),
        }
        await redis.publish(channel_for_project(project_id), json.dumps(message))
