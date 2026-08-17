from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AgentType, ModelTier
from app.db.base import Base, TimestampMixin, uuid_pk


class Agent(TimestampMixin, Base):
    """Small, mostly-static catalog of agent 'roles' available to the
    orchestrator (seeded once - see scripts/seed_demo_project.py). Kept as
    a table rather than an enum-only concept so system prompts / default
    tiers can be tuned per-deployment without a code change."""

    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    agent_type: Mapped[AgentType] = mapped_column(SAEnum(AgentType, name="agent_type"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    default_model_tier: Mapped[ModelTier] = mapped_column(
        SAEnum(ModelTier, name="model_tier"), nullable=False
    )
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AgentRun(TimestampMixin, Base):
    """One execution of an agent against one task. This is the row that
    token_usage/tool_calls hang off of, and the thing the frontend's right
    panel (docs/16-frontend.md) renders live."""

    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), default="running", nullable=False)
    model_tier: Mapped[ModelTier | None] = mapped_column(SAEnum(ModelTier, name="model_tier_run"), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decision_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_context_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)

    task: Mapped["Task"] = relationship(back_populates="agent_runs")
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        back_populates="agent_run", cascade="all, delete-orphan"
    )
