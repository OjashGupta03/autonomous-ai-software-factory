"""Human-in-the-loop endpoints (spec section 19)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_arq_pool, get_current_user
from app.core.constants import ApprovalStatus
from app.db.session import get_db
from app.models.user import User
from app.schemas.approval import ApprovalDecision, ApprovalRead
from app.services import approval_service

router = APIRouter(prefix="/projects/{project_id}/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalRead])
async def list_pending_approvals(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list:
    return await approval_service.get_pending_for_project(db, project_id)


@router.post("/{approval_id}/decide", response_model=ApprovalRead)
async def decide_approval(
    project_id: uuid.UUID, approval_id: uuid.UUID, decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
    arq_pool=Depends(get_arq_pool),
) -> object:
    approval = await approval_service.resolve_approval(db, approval_id, decision.decision, current_user.id, decision.note)
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")

    if decision.decision in (ApprovalStatus.APPROVED, ApprovalStatus.MODIFIED) and approval.task_id is not None:
        from app.services import task_service

        await task_service.reset_for_retry(db, approval.task_id, escalate_to_debugger=False)

    if decision.decision in (ApprovalStatus.APPROVED, ApprovalStatus.MODIFIED):
        # Resume the orchestrator loop - it will pick up wherever the
        # scheduler finds work next (see ProjectRunner.run_or_resume).
        await arq_pool.enqueue_job("run_project_job", str(project_id))

    return approval
