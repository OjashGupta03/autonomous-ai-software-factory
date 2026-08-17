from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel

from app.core.constants import ApprovalStatus, ApprovalType
from app.schemas.common import TimestampedSchema


class ApprovalRead(TimestampedSchema):
    project_id: uuid.UUID
    task_id: uuid.UUID | None
    approval_type: ApprovalType
    status: ApprovalStatus
    requested_reason: str
    decision_note: str | None
    decided_at: dt.datetime | None


class ApprovalDecision(BaseModel):
    decision: ApprovalStatus
    note: str | None = None
    modified_instruction: str | None = None
