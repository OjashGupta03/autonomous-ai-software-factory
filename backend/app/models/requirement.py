from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, JSON, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk


class Requirement(TimestampMixin, Base):
    """The raw natural-language requirement plus any structured constraints
    the user supplied at creation time (budget, preferred stack, etc.).
    Kept separate from Project so a project can, in principle, be re-scoped
    without losing the original ask."""

    __tablename__ = "requirements"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="requirements")
