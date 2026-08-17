"""File/artifact viewer endpoints (spec section 24)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.file import Artifact, File
from app.models.user import User
from app.schemas.file import ArtifactRead, FileMeta, FileRead
from app.tools.db_tools import FileDiffTool

router = APIRouter(prefix="/projects/{project_id}", tags=["files"])


@router.get("/files", response_model=list[FileMeta])
async def list_files(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[File]:
    result = await db.execute(select(File).where(File.project_id == project_id).order_by(File.path, File.version.desc()))
    latest: dict[str, File] = {}
    for f in result.scalars().all():
        if f.path not in latest or f.version > latest[f.path].version:
            latest[f.path] = f
    return sorted(latest.values(), key=lambda f: f.path)


@router.get("/files/content", response_model=FileRead)
async def get_file_content(
    project_id: uuid.UUID, path: str,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> File:
    result = await db.execute(
        select(File).where(File.project_id == project_id, File.path == path).order_by(File.version.desc())
    )
    f = result.scalars().first()
    if f is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    return f


@router.get("/files/diff")
async def get_file_diff(
    project_id: uuid.UUID, path: str, from_version: int | None = None, to_version: int | None = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    tool = FileDiffTool(db, project_id)
    result = await tool.run(path=path, from_version=from_version, to_version=to_version)
    if not result.success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.error)
    return result.output


@router.get("/artifacts", response_model=list[ArtifactRead])
async def list_artifacts(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[Artifact]:
    result = await db.execute(select(Artifact).where(Artifact.project_id == project_id).order_by(Artifact.created_at.desc()))
    return list(result.scalars().all())
