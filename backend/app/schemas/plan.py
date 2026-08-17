from __future__ import annotations

import uuid

from app.schemas.common import TimestampedSchema


class ProjectPlanRead(TimestampedSchema):
    project_id: uuid.UUID
    version: int
    architecture_summary: str
    milestones: list | None
    tech_stack: dict | None
    is_active: bool
