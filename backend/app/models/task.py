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
    """A single unit of work in the project DAG. `task_type` drives both
    scheduling (app/orchestrator/scheduler.py) and model routing
    (app/orchestrator/model_router.py) - it is what lets the orchestrator
    decide "does this even need an LLM?" without asking one."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("project_plans.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[TaskType] = mapped_column(SAEnum(TaskType, name="task_type"), nullable=False)
    assigned_agent_type: Mapped[AgentType | None] = mapped_column(
        SAEnum(AgentType, name="agent_type_ref"), nullable=True
    )
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status"), default=TaskStatus.PENDING, nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    context_budget_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Structured, Planner-authored payload for DETERMINISTIC-tier tasks
    # (e.g. {"action": "create_files", "files": {"path": "content", ...}}
    # or {"action": "install", "manager": "npm", "packages": [...]}).
    # The Planner call (already an LLM call) decides *what* a scaffold
    # step contains; executing it is then pure mechanical application of
    # this payload with zero further LLM calls. See
    # app/services/agent_execution_service.py::_execute_deterministic_task.
    deterministic_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)

    project: Mapped["Project"] = relationship(back_populates="tasks")
    dependencies: Mapped[list["TaskDependency"]] = relationship(
        foreign_keys="TaskDependency.task_id", cascade="all, delete-orphan"
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="task")


class TaskDependency(Base):
    """Edge in the task DAG: `task_id` depends on `depends_on_task_id`
    (i.e. depends_on must reach `completed` before task_id becomes ready).
    A plain join table - deliberately no ORM back-ref soup here, the
    scheduler reads these as flat (task_id, depends_on_task_id) tuples."""

    __tablename__ = "task_dependencies"
    __table_args__ = (UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
