"""Project CRUD + the "start execution" action that kicks off the orchestrator."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_arq_pool, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectRead, ProjectSummary
from app.services import project_service, token_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ProjectRead:
    project = await project_service.create_project(db, current_user.id, data)
    return project


@router.get("", response_model=list[ProjectSummary])
async def list_projects(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[ProjectSummary]:
    projects = await project_service.list_projects(db, current_user.id)
    summaries = []
    for p in projects:
        metrics = await token_service.get_project_metrics(db, p.id)
        summaries.append(ProjectSummary(
            **ProjectRead.model_validate(p).model_dump(),
            tasks_total=metrics.tasks_total, tasks_completed=metrics.tasks_completed,
            tasks_failed=metrics.tasks_total - metrics.tasks_completed if metrics.tasks_total else 0,
            total_cost_usd=metrics.estimated_cost_usd, total_tokens=metrics.total_tokens, llm_calls=metrics.llm_calls,
        ))
    return summaries


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ProjectRead:
    project = await project_service.get_project(db, project_id)
    if project is None or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


@router.post("/{project_id}/start", status_code=status.HTTP_202_ACCEPTED)
async def start_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    arq_pool=Depends(get_arq_pool),
) -> dict:
    """Enqueues `run_project_job` on the worker pool and returns
    immediately (202) - a full project run can take far longer than an
    HTTP request should be held open for. Progress is observed via
    GET /projects/{id}/events (SSE), not this response."""
    project = await project_service.get_project(db, project_id)
    if project is None or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    await arq_pool.enqueue_job("run_project_job", str(project_id))
    return {"status": "queued", "project_id": str(project_id)}

import io
import zipfile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from app.models.file import File

@router.get("/{project_id}/download")
async def download_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    project = await project_service.get_project(db, project_id)
    if project is None or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        
    stmt = select(File).filter(File.project_id == project_id).distinct(File.path).order_by(File.path, File.version.desc())
    result = await db.execute(stmt)
    files = result.scalars().all()
    
    if not files:
        raise HTTPException(status_code=404, detail="No files found for this project")
        
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, False) as zip_file:
        for f in files:
            zip_file.writestr(f.path, f.content)
            
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{project.name}.zip"'}
    )
