from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import ErrorCategory
from app.db.base import Base, TimestampMixin, uuid_pk


class ErrorRecord(TimestampMixin, Base):
    """A single failure, deterministically classified (see
    app/orchestrator/failure_recovery.py::classify_error). The category is
    what drives retry-vs-escalate, not an LLM call."""

    __tablename__ = "errors"

    id: Mapped[uuid.UUID] = uuid_pk()
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[ErrorCategory] = mapped_column(
        SAEnum(ErrorCategory, name="error_category"), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)


class RetryAttempt(TimestampMixin, Base):
    __tablename__ = "retry_attempts"

    id: Mapped[uuid.UUID] = uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    previous_error_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("errors.id", ondelete="SET NULL"), nullable=True
    )
