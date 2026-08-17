"""Token/cost analytics endpoints (spec sections 16, 23)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.metrics import NaiveVsOptimizedComparison, ProjectMetrics, TokenUsageRead
from app.services import token_service

router = APIRouter(prefix="/projects/{project_id}/metrics", tags=["metrics"])


@router.get("", response_model=ProjectMetrics)
async def get_metrics(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ProjectMetrics:
    return await token_service.get_project_metrics(db, project_id)


@router.get("/comparison", response_model=NaiveVsOptimizedComparison)
async def get_naive_comparison(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> NaiveVsOptimizedComparison:
    return await token_service.get_naive_comparison(db, project_id)


@router.get("/token-usage", response_model=list[TokenUsageRead])
async def get_token_usage(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list:
    from sqlalchemy import select

    from app.models.token_usage import TokenUsage

    result = await db.execute(
        select(TokenUsage).where(TokenUsage.project_id == project_id).order_by(TokenUsage.created_at.desc())
    )
    return list(result.scalars().all())
