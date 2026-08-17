from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base for any schema that is built directly from an ORM row."""
    model_config = ConfigDict(from_attributes=True)


class TimestampedSchema(ORMModel):
    id: uuid.UUID
    created_at: dt.datetime
    updated_at: dt.datetime


class Page(BaseModel):
    total: int
    items: list
