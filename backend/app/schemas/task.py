from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel

from app.core.constants import AgentType, TaskStatus, TaskType
from app.schemas.common import TimestampedSchema


class TaskRead(TimestampedSchema):
    project_id: uuid.UUID
    plan_id: uuid.UUID | None
    title: str
    description: str
    task_type: TaskType
    assigned_agent_type: AgentType | None
    status: TaskStatus
    priority: int
    attempt_count: int
    max_attempts: int
    started_at: dt.datetime | None
    completed_at: dt.datetime | None
    depends_on: list[uuid.UUID] = []


class TaskDetail(TaskRead):
    """Everything the task-detail drawer in the DAG UI needs in one call
    (spec section 21): files touched, latest error, latest test outcome."""

    files_modified: list[str] = []
    latest_error: str | None = None
    tokens_used: int = 0
    cost_usd: float = 0.0


class TaskGraphNode(BaseModel):
    id: uuid.UUID
    title: str
    status: TaskStatus
    task_type: TaskType
    depends_on: list[uuid.UUID]


class TaskGraphResponse(BaseModel):
    project_id: uuid.UUID
    nodes: list[TaskGraphNode]
