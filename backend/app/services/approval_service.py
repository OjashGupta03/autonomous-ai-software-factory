"""Human-in-the-loop checkpoints (docs/13-human-in-the-loop.md)."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ApprovalStatus, ApprovalType
from app.models.approval import Approval


async def create_approval(
    db: AsyncSession,
    project_id: uuid.UUID,
    approval_type: ApprovalType,
    reason: str,
    task_id: uuid.UUID | None = None,
) -> Approval:
    approval = Approval(
        project_id=project_id, task_id=task_id, approval_type=approval_type, requested_reason=reason
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return approval


async def get_pending_for_project(db: AsyncSession, project_id: uuid.UUID) -> list[Approval]:
    result = await db.execute(
        select(Approval).where(Approval.project_id == project_id, Approval.status == ApprovalStatus.PENDING)
    )
    return list(result.scalars().all())


async def resolve_approval(
    db: AsyncSession,
    approval_id: uuid.UUID,
    decision: ApprovalStatus,
    decided_by: uuid.UUID,
    note: str | None = None,
) -> Approval | None:
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if approval is None:
        return None
    approval.status = decision
    approval.decided_by = decided_by
    approval.decision_note = note
    approval.decided_at = dt.datetime.now(dt.timezone.utc)
    await db.commit()
    await db.refresh(approval)
    return approval
