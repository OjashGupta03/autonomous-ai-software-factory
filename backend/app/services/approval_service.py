from __future__ import annotations

import datetime as dt
import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ApprovalStatus, ApprovalType
from app.models.approval import Approval


async def get_pending_for_project(db: AsyncSession, project_id: uuid.UUID) -> Sequence[Approval]:
    result = await db.execute(
        select(Approval)
        .where(
            Approval.project_id == project_id,
            Approval.status == ApprovalStatus.PENDING
        )
        .order_by(Approval.created_at.desc())
    )
    return result.scalars().all()


async def resolve_approval(
    db: AsyncSession,
    approval_id: uuid.UUID,
    decision: ApprovalStatus,
    user_id: uuid.UUID,
    note: str | None = None
) -> Approval | None:
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalars().first()
    
    if approval:
        approval.status = decision
        approval.decided_by = user_id
        approval.decision_note = note
        approval.decided_at = dt.datetime.utcnow()
        await db.commit()
        await db.refresh(approval)
        
    return approval


async def create_approval(
    db: AsyncSession,
    project_id: uuid.UUID,
    approval_type: ApprovalType,
    reason: str,
    task_id: uuid.UUID | None = None,
) -> Approval:
    approval = Approval(
        project_id=project_id,
        approval_type=approval_type,
        requested_reason=reason,
        task_id=task_id,
        status=ApprovalStatus.PENDING,
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return approval
