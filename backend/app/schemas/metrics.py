from __future__ import annotations

import uuid

from pydantic import BaseModel


class TokenUsageRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    task_id: uuid.UUID | None
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cache_hit: bool


class ModelUsageAggregate(BaseModel):
    """The aggregation that replaces a standalone `model_usage` table -
    computed on read in services/token_service.py."""
    model: str
    provider: str
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class ProjectMetrics(BaseModel):
    """The headline numbers for spec section 16 (per-project metrics card)."""

    project_id: uuid.UUID
    llm_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    tasks_completed: int
    tasks_total: int
    retries: int
    cache_hits: int
    parallel_tasks_peak: int
    by_model: list[ModelUsageAggregate]


class NaiveVsOptimizedComparison(BaseModel):
    """The 'tokens saved' comparison from spec section 16/23. `naive_*`
    fields are a documented ESTIMATE (see docs/07-token-optimization.md),
    not a measurement - the naive pipeline never actually ran."""

    project_id: uuid.UUID
    naive_llm_calls: int
    naive_tokens: int
    optimized_llm_calls: int
    optimized_tokens: int
    tokens_saved: int
    tokens_saved_pct: float
    calls_saved: int
    calls_saved_pct: float
