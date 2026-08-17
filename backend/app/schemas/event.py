from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel


class ProjectEventRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    event_type: str
    payload: dict
    created_at: dt.datetime
