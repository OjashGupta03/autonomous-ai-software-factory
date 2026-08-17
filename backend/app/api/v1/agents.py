"""Agent catalog + agent-run history endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.agent import Agent, AgentRun
from app.models.task import Task
from app.models.user import User
from app.schemas.agent import AgentRead, AgentRunRead

router = APIRouter(tags=["agents"])


@router.get("/agents", response_model=list[AgentRead])
async def list_agents(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[Agent]:
    result = await db.execute(select(Agent).where(Agent.is_active.is_(True)))
    return list(result.scalars().all())


@router.get("/projects/{project_id}/agent-runs", response_model=list[AgentRunRead])
async def list_agent_runs(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[AgentRun]:
    result = await db.execute(
        select(AgentRun).join(Task, Task.id == AgentRun.task_id).where(Task.project_id == project_id)
        .order_by(AgentRun.created_at.desc())
    )
    return list(result.scalars().all())
