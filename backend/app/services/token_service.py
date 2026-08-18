from __future__ import annotations

import uuid
import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.token_usage import TokenUsage
from app.orchestrator.pricing import calculate_cost
from app.orchestrator.naive_comparison import compare
from app.schemas.metrics import ModelUsageAggregate, NaiveVsOptimizedComparison, ProjectMetrics


async def record_usage(
    db: AsyncSession,
    project_id: uuid.UUID,
    model_name: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    task_id: uuid.UUID | None = None,
    agent_run_id: uuid.UUID | None = None,
    cache_hit: bool = False,
) -> None:
    cost = calculate_cost(model_name, input_tokens, output_tokens)
    record = TokenUsage(
        project_id=project_id,
        task_id=task_id,
        agent_run_id=agent_run_id,
        model=model_name,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        cache_hit=cache_hit,
    )
    db.add(record)
    await db.commit()


async def get_project_metrics(db: AsyncSession, project_id: uuid.UUID) -> ProjectMetrics:
    result = await db.execute(
        select(
            func.count(TokenUsage.id).label("llm_calls"),
            func.sum(TokenUsage.input_tokens).label("input_tokens"),
            func.sum(TokenUsage.output_tokens).label("output_tokens"),
            func.sum(TokenUsage.cost_usd).label("cost_usd"),
            func.sum(func.cast(TokenUsage.cache_hit, sa.Integer)).label("cache_hits")
        )
        .where(TokenUsage.project_id == project_id)
    )
    row = result.first()
    llm_calls = row.llm_calls or 0
    input_tokens = row.input_tokens or 0
    output_tokens = row.output_tokens or 0
    total_tokens = input_tokens + output_tokens
    cost_usd = row.cost_usd or 0.0
    cache_hits = row.cache_hits or 0

    from app.core.constants import TaskStatus
    task_result = await db.execute(
        select(
            func.count(Task.id).label("total"),
            func.sum(
                func.cast(Task.status.in_([TaskStatus.COMPLETED, TaskStatus.SKIPPED]), sa.Integer)
            ).label("completed"),
            func.sum(Task.attempt_count).label("retries")
        ).where(Task.project_id == project_id)
    )
    t_row = task_result.first()
    tasks_total = t_row.total or 0
    tasks_completed = t_row.completed or 0
    retries = t_row.retries or 0
    
    model_result = await db.execute(
        select(
            TokenUsage.model,
            TokenUsage.provider,
            func.count(TokenUsage.id).label("calls"),
            func.sum(TokenUsage.input_tokens).label("input_tokens"),
            func.sum(TokenUsage.output_tokens).label("output_tokens"),
            func.sum(TokenUsage.cost_usd).label("cost_usd"),
        )
        .where(TokenUsage.project_id == project_id)
        .group_by(TokenUsage.model, TokenUsage.provider)
    )
    
    by_model = []
    for m in model_result.all():
        by_model.append(ModelUsageAggregate(
            model=m.model,
            provider=m.provider,
            calls=m.calls or 0,
            input_tokens=m.input_tokens or 0,
            output_tokens=m.output_tokens or 0,
            cost_usd=m.cost_usd or 0.0
        ))

    return ProjectMetrics(
        project_id=project_id,
        llm_calls=llm_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=cost_usd,
        tasks_completed=tasks_completed,
        tasks_total=tasks_total,
        retries=retries,
        cache_hits=cache_hits,
        parallel_tasks_peak=0,
        by_model=by_model,
    )


async def get_naive_comparison(db: AsyncSession, project_id: uuid.UUID) -> NaiveVsOptimizedComparison:
    metrics = await get_project_metrics(db, project_id)
    
    comp = compare(
        task_count=metrics.tasks_total,
        optimized_llm_calls=metrics.llm_calls,
        optimized_input_tokens=metrics.input_tokens,
        optimized_output_tokens=metrics.output_tokens,
    )
    
    return NaiveVsOptimizedComparison(
        project_id=project_id,
        naive_llm_calls=comp.naive.llm_calls,
        naive_tokens=comp.naive.total_tokens,
        optimized_llm_calls=metrics.llm_calls,
        optimized_tokens=metrics.total_tokens,
        tokens_saved=comp.tokens_saved,
        tokens_saved_pct=comp.tokens_saved_pct,
        calls_saved=comp.calls_saved,
        calls_saved_pct=comp.calls_saved_pct,
    )
