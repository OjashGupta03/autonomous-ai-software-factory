from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, JSON, String
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, uuid_pk
import datetime as dt
from sqlalchemy import DateTime, func


class ProjectEvent(Base):
    """Append-only event log backing the SSE live-update stream
    (docs/22). Every event the frontend can render live is durably
    written here first, then published to Redis for fan-out - so a client
    that connects late can replay recent history instead of missing it."""

    __tablename__ = "project_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
