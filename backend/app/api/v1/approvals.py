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

        # FIX: `decision.modified_instruction` (and `.note`, as a
        # fallback) used to be accepted by this endpoint and then never
        # passed anywhere - reset_for_retry didn't take it, and the next
        # execution of the task always re-ran task.description verbatim.
        # docs/13-human-in-the-loop.md documents "modified" as covering
        # 'retry with a modified instruction' via the note field "which
        # becomes part of the task's context on the next attempt" - this
        # now actually makes that true. Only threaded through on an
        # explicit MODIFIED decision, so a plain "approve and retry"
        # keeps behaving exactly as before.
        instruction_override = None
        if decision.decision == ApprovalStatus.MODIFIED:
            instruction_override = decision.modified_instruction or decision.note

        await task_service.reset_for_retry(
            db, approval.task_id, escalate_to_debugger=False, instruction_override=instruction_override,
        )

    if decision.decision in (ApprovalStatus.APPROVED, ApprovalStatus.MODIFIED):
        await arq_pool.enqueue_job("run_project_job", str(project_id))

    return approval
