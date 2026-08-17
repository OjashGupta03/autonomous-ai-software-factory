from __future__ import annotations

import uuid

from app.schemas.common import TimestampedSchema


class RequirementRead(TimestampedSchema):
    project_id: uuid.UUID
    raw_text: str
    constraints: dict | None
