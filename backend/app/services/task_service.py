"""
Task + task-dependency persistence, and the bridge to the DB-free
scheduler (app/orchestrator/scheduler.py). This module is the only place
that converts between SQLAlchemy `Task` rows and the scheduler's plain
`TaskNode` dataclass, keeping the scheduler itself framework-agnostic.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import AgentType, TaskStatus, TaskType
from app.models.task import Task, TaskDependency
from app.orchestrator.scheduler import TaskNode, validate_dag


async def create_tasks_from_plan(
    db: AsyncSession,
    project_id: uuid.UUID,
    plan_id: uuid.UUID | None,
    proposed_tasks: list[dict],
) -> list[Task]:
    """`proposed_tasks` is the Planner's structured DAG proposal:
    [{"key": "T1", "title": ..., "description": ..., "task_type": ...,
      "depends_on": ["T0"], "priority": 0}, ...]
    `key` is the Planner's own local id (e.g. "T1") used only to express
    edges within this call; real DB UUIDs are assigned here. The graph is
    validated (cycle check) BEFORE anything is written, so a bad proposal
    never lands half-committed.
    """
    nodes = [
        TaskNode(id=t["key"], status=TaskStatus.PENDING, depends_on=tuple(t.get("depends_on", [])))
        for t in proposed_tasks
    ]
    validate_dag(nodes)  # raises CyclicDependencyError / ValueError on a bad graph

    key_to_task: dict[str, Task] = {}
    created: list[Task] = []
    for t in proposed_tasks:
        task = Task(
            project_id=project_id,
            plan_id=plan_id,
            title=t["title"],
            description=t["description"],
            task_type=TaskType(t["task_type"]),
            assigned_agent_type=AgentType(t["agent_type"]) if t.get("agent_type") else None,
            priority=t.get("priority", 0),
            max_attempts=t.get("max_attempts", 3),
            deterministic_payload=t.get("deterministic_payload"),
        )
        db.add(task)
        created.append(task)
        key_to_task[t["key"]] = task  # .id is unset until the flush below

    await db.flush()  # assigns Task.id for every row added above

    for t in proposed_tasks:
        task_row = key_to_task[t["key"]]
        for dep_key in t.get("depends_on", []):
            dep_row = key_to_task[dep_key]
            db.add(TaskDependency(task_id=task_row.id, depends_on_task_id=dep_row.id))

    await db.commit()
    for task in created:
        await db.refresh(task)
    return created


async def list_tasks(db: AsyncSession, project_id: uuid.UUID) -> list[Task]:
    result = await db.execute(
        select(Task).where(Task.project_id == project_id).options(selectinload(Task.dependencies))
    )
    return list(result.scalars().unique().all())


async def get_task(db: AsyncSession, task_id: uuid.UUID) -> Task | None:
    result = await db.execute(select(Task).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def to_scheduler_nodes(db: AsyncSession, project_id: uuid.UUID) -> list[TaskNode]:
    tasks = await list_tasks(db, project_id)
    return [
        TaskNode(
            id=str(t.id),
            status=t.status,
            depends_on=tuple(str(d.depends_on_task_id) for d in t.dependencies),
            priority=t.priority,
        )
        for t in tasks
    ]


async def mark_running(db: AsyncSession, task_id: uuid.UUID) -> None:
    task = await get_task(db, task_id)
    if task is None:
        return
    task.status = TaskStatus.RUNNING
    task.started_at = dt.datetime.now(dt.timezone.utc)
    task.attempt_count += 1
    await db.commit()


async def mark_completed(db: AsyncSession, task_id: uuid.UUID) -> None:
    task = await get_task(db, task_id)
    if task is None:
        return
    task.status = TaskStatus.COMPLETED
    task.completed_at = dt.datetime.now(dt.timezone.utc)
    await db.commit()


async def mark_failed(db: AsyncSession, task_id: uuid.UUID) -> None:
    task = await get_task(db, task_id)
    if task is None:
        return
    task.status = TaskStatus.FAILED
    await db.commit()


async def reset_for_retry(db: AsyncSession, task_id: uuid.UUID, escalate_to_debugger: bool = False) -> None:
    task = await get_task(db, task_id)
    if task is None:
        return
    task.status = TaskStatus.PENDING
    if escalate_to_debugger:
        task.assigned_agent_type = AgentType.DEBUGGER
    await db.commit()


async def mark_needs_approval(db: AsyncSession, task_id: uuid.UUID) -> None:
    task = await get_task(db, task_id)
    if task is None:
        return
    task.status = TaskStatus.NEEDS_APPROVAL
    await db.commit()


async def set_blocked(db: AsyncSession, task_ids: list[str]) -> None:
    if not task_ids:
        return
    for raw_id in task_ids:
        task = await get_task(db, uuid.UUID(raw_id))
        if task is not None:
            task.status = TaskStatus.BLOCKED
    await db.commit()
