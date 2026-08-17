from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, JSON, String, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk


class ToolCall(TimestampMixin, Base):
    """Record of a single deterministic tool invocation (file write, test
    run, lint, shell command, ...). Tool calls are *not* LLM calls and
    carry no token cost, but they are tracked for observability and so the
    frontend can show 'files modified' / 'tools used' per agent run."""

    __tablename__ = "tool_calls"

    id: Mapped[uuid.UUID] = uuid_pk()
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    agent_run: Mapped["AgentRun"] = relationship(back_populates="tool_calls")
