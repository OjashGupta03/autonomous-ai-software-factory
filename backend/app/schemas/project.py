from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.core.constants import ProjectStatus
from app.schemas.common import TimestampedSchema


class ProjectCreate(BaseModel):
    """The single entry point described in spec section 20 ("Create
    Project"): a name, a natural-language requirement, and optional
    constraints. Everything downstream (architecture, tasks, agents) is
    derived from this by the Planner - the user never hand-authors a DAG."""

    name: str = Field(min_length=1, max_length=255)
    requirement: str = Field(min_length=10, description="Natural-language product/software requirement")
    preferred_stack: dict | None = None
    constraints: dict | None = None
    token_budget: int = Field(default=500_000, gt=0)


class ProjectRead(TimestampedSchema):
    name: str
    description: str | None
    status: ProjectStatus
    preferred_stack: dict | None
    token_budget: int
    current_iteration: int
    owner_id: uuid.UUID


class ProjectSummary(ProjectRead):
    """ProjectRead plus the rolled-up counters the Dashboard needs, so the
    frontend does not have to make N+1 calls per project card."""

    tasks_total: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    llm_calls: int = 0
