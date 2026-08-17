"""Live SSE event stream (spec section 22)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user, get_redis
from app.db.session import get_db
from app.events.sse import project_event_stream
from app.models.user import User

router = APIRouter(prefix="/projects/{project_id}/events", tags=["events"])


@router.get("")
async def stream_events(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    return StreamingResponse(
        project_event_stream(db, redis, project_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
