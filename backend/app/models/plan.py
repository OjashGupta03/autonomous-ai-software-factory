from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, JSON, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk


class ProjectPlan(TimestampMixin, Base):
    """Output of the Planner Agent: architecture + milestones + the task
    list it proposed. Versioned because re-planning (e.g. after a human
    rejects a plan) should not destroy history."""

    __tablename__ = "project_plans"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    architecture_summary: Mapped[str] = mapped_column(Text, nullable=False)
    milestones: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tech_stack: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="plans")
