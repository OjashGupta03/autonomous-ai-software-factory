"""
Token/cost accounting (docs/07-token-optimization.md).

Every LLM call recorded via `record_usage` is the single source of truth
for all analytics: per-project totals, per-model breakdowns, and the
naive-vs-optimized comparison are all *queries* over `token_usage`, never
a separately maintained counter that could drift from it.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import TaskStatus
from app.models.task import Task
from app.models.token_usage import TokenUsage
from app.orchestrator.naive_comparison import compare as naive_compare
from app.orchestrator.pricing import calculate_cost
from app.schemas.metrics import ModelUsageAggregate, NaiveVsOptimizedComparison, ProjectMetrics


async def record_usage(
    db: AsyncSession,
    project_id: uuid.UUID,
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    task_id: uuid.UUID | None = None,
    agent_run_id: uuid.UUID | None = None,
    cache_hit: bool = False,
) -> TokenUsage:
    cost = 0.0 if cache_hit else calculate_cost(model, input_tokens, output_tokens)
    row = TokenUsage(
        project_id=project_id,
        task_id=task_id,
        agent_run_id=agent_run_id,
        model=model,
        provider=provider,
        input_tokens=0 if cache_hit else input_tokens,
        output_tokens=0 if cache_hit else output_tokens,
        cost_usd=cost,
        cache_hit=cache_hit,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_project_metrics(db: AsyncSession, project_id: uuid.UUID) -> ProjectMetrics:
    usage_result = await db.execute(select(TokenUsage).where(TokenUsage.project_id == project_id))
    usage_rows = list(usage_result.scalars().all())

    tasks_result = await db.execute(select(Task).where(Task.project_id == project_id))
    tasks = list(tasks_result.scalars().all())

    by_model: dict[tuple[str, str], ModelUsageAggregate] = {}
    for u in usage_rows:
        key = (u.model, u.provider)
        agg = by_model.get(key) or ModelUsageAggregate(
            model=u.model, provider=u.provider, calls=0, input_tokens=0, output_tokens=0, cost_usd=0.0
        )
        agg.calls += 1
        agg.input_tokens += u.input_tokens
        agg.output_tokens += u.output_tokens
        agg.cost_usd += u.cost_usd
        by_model[key] = agg

    retries = sum(max(0, t.attempt_count - 1) for t in tasks)

    return ProjectMetrics(
        project_id=project_id,
        llm_calls=len([u for u in usage_rows if not u.cache_hit]),
        input_tokens=sum(u.input_tokens for u in usage_rows),
        output_tokens=sum(u.output_tokens for u in usage_rows),
        total_tokens=sum(u.input_tokens + u.output_tokens for u in usage_rows),
        estimated_cost_usd=round(sum(u.cost_usd for u in usage_rows), 4),
        tasks_completed=len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
        tasks_total=len(tasks),
        retries=retries,
        cache_hits=len([u for u in usage_rows if u.cache_hit]),
        parallel_tasks_peak=0,  # populated from project_events by the metrics API if needed; see docs/16
        by_model=list(by_model.values()),
    )


async def get_naive_comparison(db: AsyncSession, project_id: uuid.UUID) -> NaiveVsOptimizedComparison:
    metrics = await get_project_metrics(db, project_id)
    result = naive_compare(
        task_count=metrics.tasks_total,
        optimized_llm_calls=metrics.llm_calls,
        optimized_input_tokens=metrics.input_tokens,
        optimized_output_tokens=metrics.output_tokens,
    )
    return NaiveVsOptimizedComparison(
        project_id=project_id,
        naive_llm_calls=result.naive.llm_calls,
        naive_tokens=result.naive.total_tokens,
        optimized_llm_calls=result.optimized_llm_calls,
        optimized_tokens=result.optimized_total_tokens,
        tokens_saved=result.tokens_saved,
        tokens_saved_pct=result.tokens_saved_pct,
        calls_saved=result.calls_saved,
        calls_saved_pct=result.calls_saved_pct,
    )
