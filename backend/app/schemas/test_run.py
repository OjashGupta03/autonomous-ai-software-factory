from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel

from app.schemas.common import TimestampedSchema


class TestResultRead(BaseModel):
    id: uuid.UUID
    test_name: str
    status: str
    duration_ms: float
    message: str | None


class TestRunRead(TimestampedSchema):
    project_id: uuid.UUID
    task_id: uuid.UUID | None
    trigger: str
    status: str
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    results: list[TestResultRead] = []
