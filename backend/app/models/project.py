from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, JSON
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ProjectStatus
from app.db.base import Base, TimestampMixin, uuid_pk


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, name="project_status"),
        default=ProjectStatus.DRAFT,
        nullable=False,
        index=True,
    )
    preferred_stack: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    token_budget: Mapped[int] = mapped_column(Integer, default=500_000, nullable=False)
    current_iteration: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    plans: Mapped[list["ProjectPlan"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
