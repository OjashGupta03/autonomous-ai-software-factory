from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ProjectStatus
from app.models.project import Project
from app.models.requirement import Requirement
from app.schemas.project import ProjectCreate


async def create_project(db: AsyncSession, owner_id: uuid.UUID, data: ProjectCreate) -> Project:
    project = Project(
        owner_id=owner_id,
        name=data.name,
        description=data.requirement[:250] + ("..." if len(data.requirement) > 250 else ""),
        status=ProjectStatus.DRAFT,
        preferred_stack=data.preferred_stack,
        token_budget=data.token_budget,
    )
    db.add(project)
    await db.flush()

    requirement = Requirement(
        project_id=project.id,
        raw_text=data.requirement,
        constraints=data.constraints,
    )
    db.add(requirement)
    await db.commit()
    await db.refresh(project)
    return project


async def list_projects(db: AsyncSession, owner_id: uuid.UUID) -> Sequence[Project]:
    result = await db.execute(select(Project).where(Project.owner_id == owner_id).order_by(Project.created_at.desc()))
    return result.scalars().all()


async def get_project(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    result = await db.execute(select(Project).where(Project.id == project_id))
    return result.scalars().first()


async def get_active_requirement(db: AsyncSession, project_id: uuid.UUID) -> Requirement | None:
    result = await db.execute(
        select(Requirement)
        .where(Requirement.project_id == project_id)
        .order_by(Requirement.created_at.desc())
    )
    return result.scalars().first()


async def set_status(db: AsyncSession, project_id: uuid.UUID, status: ProjectStatus) -> None:
    project = await get_project(db, project_id)
    if project:
        project.status = status
        await db.commit()
