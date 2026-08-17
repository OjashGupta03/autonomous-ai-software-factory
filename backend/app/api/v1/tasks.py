"""Task + task-graph endpoints (spec section 21, "Task Graph UI")."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.agent import AgentRun
from app.models.error import ErrorRecord
from app.models.file import File
from app.models.user import User
from app.schemas.task import TaskDetail, TaskGraphNode, TaskGraphResponse, TaskRead
from app.services import project_service, task_service

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


async def _check_ownership(db: AsyncSession, project_id: uuid.UUID, user: User) -> None:
    project = await project_service.get_project(db, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[TaskRead]:
    await _check_ownership(db, project_id, current_user)
    tasks = await task_service.list_tasks(db, project_id)
    return [
        TaskRead(**{**_task_to_dict(t), "depends_on": [d.depends_on_task_id for d in t.dependencies]})
        for t in tasks
    ]


@router.get("/graph", response_model=TaskGraphResponse)
async def get_task_graph(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> TaskGraphResponse:
    await _check_ownership(db, project_id, current_user)
    tasks = await task_service.list_tasks(db, project_id)
    nodes = [
        TaskGraphNode(
            id=t.id, title=t.title, status=t.status, task_type=t.task_type,
            depends_on=[d.depends_on_task_id for d in t.dependencies],
        )
        for t in tasks
    ]
    return TaskGraphResponse(project_id=project_id, nodes=nodes)


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task_detail(
    project_id: uuid.UUID, task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> TaskDetail:
    await _check_ownership(db, project_id, current_user)
    task = await task_service.get_task(db, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    files_result = await db.execute(select(File.path).where(File.created_by_task_id == task_id))
    files_modified = [row[0] for row in files_result.all()]

    err_result = await db.execute(
        select(ErrorRecord).where(ErrorRecord.task_id == task_id).order_by(ErrorRecord.created_at.desc())
    )
    latest_error = err_result.scalars().first()

    runs_result = await db.execute(select(AgentRun).where(AgentRun.task_id == task_id))
    runs = list(runs_result.scalars().all())
    tokens_used = sum(r.tokens_input + r.tokens_output for r in runs)
    cost = sum(r.cost_usd for r in runs)

    return TaskDetail(
        **{**_task_to_dict(task), "depends_on": [d.depends_on_task_id for d in task.dependencies]},
        files_modified=files_modified,
        latest_error=latest_error.message if latest_error else None,
        tokens_used=tokens_used,
        cost_usd=cost,
    )


def _task_to_dict(task) -> dict:
    return {
        "id": task.id, "created_at": task.created_at, "updated_at": task.updated_at,
        "project_id": task.project_id, "plan_id": task.plan_id, "title": task.title,
        "description": task.description, "task_type": task.task_type,
        "assigned_agent_type": task.assigned_agent_type, "status": task.status,
        "priority": task.priority, "attempt_count": task.attempt_count, "max_attempts": task.max_attempts,
        "started_at": task.started_at, "completed_at": task.completed_at,
    }
