from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import AgentType, TaskStatus, TaskType
from app.models.task import Task, TaskDependency
from app.orchestrator.scheduler import TaskNode


async def list_tasks(db: AsyncSession, project_id: uuid.UUID) -> Sequence[Task]:
    result = await db.execute(
        select(Task).options(selectinload(Task.dependencies)).where(Task.project_id == project_id).order_by(Task.created_at.asc()).execution_options(populate_existing=True)
    )
    return result.scalars().all()


async def get_task(db: AsyncSession, task_id: uuid.UUID) -> Task | None:
    result = await db.execute(select(Task).options(selectinload(Task.dependencies)).where(Task.id == task_id).execution_options(populate_existing=True))
    return result.scalars().first()


async def create_tasks_from_plan(
    db: AsyncSession, project_id: uuid.UUID, plan_id: uuid.UUID | None, proposed_tasks: list[dict]
) -> list[Task]:
    key_to_uuid = {}
    db_tasks = []

    for t in proposed_tasks:
        task_id = uuid.uuid4()
        key_to_uuid[t["key"]] = task_id
        
        agent_type_str = t.get("agent_type")
        try:
            agent_type = AgentType(agent_type_str) if agent_type_str else None
        except ValueError:
            agent_type = AgentType.CODER
            
        try:
            task_type = TaskType(t["task_type"])
        except ValueError:
            task_type = TaskType.BACKEND_IMPLEMENTATION
        
        task = Task(
            id=task_id,
            project_id=project_id,
            plan_id=plan_id,
            title=t["title"],
            description=t["description"],
            task_type=task_type,
            assigned_agent_type=agent_type,
            priority=t.get("priority", 0),
            deterministic_payload=t.get("deterministic_payload"),
        )
        db_tasks.append(task)

    db.add_all(db_tasks)
    await db.flush()

    deps = []
    for t in proposed_tasks:
        task_id = key_to_uuid[t["key"]]
        for dep_key in t.get("depends_on", []):
            if dep_key in key_to_uuid:
                deps.append(TaskDependency(task_id=task_id, depends_on_task_id=key_to_uuid[dep_key]))
    
    if deps:
        db.add_all(deps)
    
    await db.commit()
    return db_tasks


async def to_scheduler_nodes(db: AsyncSession, project_id: uuid.UUID) -> list[TaskNode]:
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.dependencies))
        .where(Task.project_id == project_id)
        .execution_options(populate_existing=True)
    )
    tasks = result.scalars().all()

    nodes = []
    for task in tasks:
        deps = tuple(str(d.depends_on_task_id) for d in task.dependencies)
        nodes.append(
            TaskNode(id=str(task.id), status=task.status, depends_on=deps, priority=task.priority)
        )
    return nodes


async def set_blocked(db: AsyncSession, task_ids: list[str]) -> None:
    if not task_ids:
        return
    await db.execute(
        update(Task)
        .where(Task.id.in_([uuid.UUID(tid) for tid in task_ids]))
        .values(status=TaskStatus.BLOCKED)
    )
    await db.commit()


async def mark_failed(db: AsyncSession, task_id: uuid.UUID) -> None:
    task = await get_task(db, task_id)
    if task:
        task.status = TaskStatus.FAILED
        await db.commit()


async def reset_for_retry(db: AsyncSession, task_id: uuid.UUID, escalate_to_debugger: bool) -> None:
    task = await get_task(db, task_id)
    if task:
        task.status = TaskStatus.PENDING
        task.attempt_count += 1
        if escalate_to_debugger:
            task.assigned_agent_type = AgentType.DEBUGGER
        await db.commit()


async def mark_needs_approval(db: AsyncSession, task_id: uuid.UUID) -> None:
    task = await get_task(db, task_id)
    if task:
        task.status = TaskStatus.NEEDS_APPROVAL
        await db.commit()
