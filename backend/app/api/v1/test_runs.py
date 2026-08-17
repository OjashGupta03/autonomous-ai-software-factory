"""Test-run endpoints (view history; triggering a run is normally
orchestrator-driven, but exposed here too for a manual "re-run tests"
action from the frontend)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_arq_pool, get_current_user
from app.db.session import get_db
from app.models.test_run import TestRun
from app.models.user import User
from app.schemas.test_run import TestRunRead

router = APIRouter(prefix="/projects/{project_id}/tests", tags=["tests"])


@router.get("", response_model=list[TestRunRead])
async def list_test_runs(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[TestRun]:
    result = await db.execute(
        select(TestRun).where(TestRun.project_id == project_id).order_by(TestRun.created_at.desc())
    )
    return list(result.unique().scalars().all())


@router.post("/rerun", status_code=202)
async def rerun_tests(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user), arq_pool=Depends(get_arq_pool),
) -> dict:
    # Re-uses the same job as a normal orchestrator-driven run; the graph
    # will find no pending tasks (assuming the project already finished
    # its build phase) and route straight to run_integration_tests.
    await arq_pool.enqueue_job("run_project_job", str(project_id))
    return {"status": "queued"}
