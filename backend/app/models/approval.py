from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import ApprovalStatus, ApprovalType
from app.db.base import Base, TimestampMixin, uuid_pk


class Approval(TimestampMixin, Base):
    """A human-in-the-loop checkpoint. While `status == pending`, the
    orchestrator run for this project is parked (see
    app/orchestrator/runner.py::resume_after_approval) rather than
    proceeding on its own. See docs/13-human-in-the-loop.md."""

    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    approval_type: Mapped[ApprovalType] = mapped_column(
        SAEnum(ApprovalType, name="approval_type"), nullable=False
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus, name="approval_status"), default=ApprovalStatus.PENDING, nullable=False, index=True
    )
    requested_reason: Mapped[str] = mapped_column(Text, nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
