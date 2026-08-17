from __future__ import annotations

import datetime as dt
import uuid

from app.core.constants import ModelTier
from app.schemas.common import TimestampedSchema


class AgentRead(TimestampedSchema):
    name: str
    agent_type: str
    description: str
    default_model_tier: ModelTier
    is_active: bool


class AgentRunRead(TimestampedSchema):
    task_id: uuid.UUID
    agent_id: uuid.UUID | None
    status: str
    model_tier: ModelTier | None
    model_used: str | None
    decision_summary: str | None
    output_summary: str | None
    tokens_input: int
    tokens_output: int
    cost_usd: float
    cache_hit: bool
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
