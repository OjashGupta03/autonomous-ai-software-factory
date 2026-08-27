from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AgentType, TaskStatus, TaskType
from app.db.base import Base, TimestampMixin, uuid_pk


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("project_plans.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[TaskType] = mapped_column(SAEnum(TaskType, name="task_type"), nullable=False)
    assigned_agent_type: Mapped[AgentType | None] = mapped_column(SAEnum(AgentType, name="agent_type_ref"), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus, name="task_status"), default=TaskStatus.PENDING, nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    context_budget_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deterministic_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # FIX: previously a human's "Modify & retry" approval decision
    # (ApprovalDecision.modified_instruction / .note) was accepted by the
    # API and then silently dropped - nothing ever stored it, and
    # execute_task always re-ran task.description verbatim, so "modify
    # and retry" behaved identically to a plain "approve and retry". This
    # column plus the wiring in task_service.reset_for_retry and
    # agent_execution_service.execute_task closes that gap.
    human_instruction_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)

    project: Mapped["Project"] = relationship(back_populates="tasks")
    dependencies: Mapped[list["TaskDependency"]] = relationship(foreign_keys="TaskDependency.task_id", cascade="all, delete-orphan")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="task")


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
