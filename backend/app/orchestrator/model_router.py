"""
Model Router - decides, per task, "does this need an LLM at all, and if
so, which tier?" (docs/08-model-routing.md).

This module is deliberately pure Python with no LangChain/network
dependency: it maps (task_type, attempt state) -> a ModelTier using fixed
rules, not a model call. The actual provider/model-name resolution for a
tier lives in app/orchestrator/llm_clients.py, which *is* allowed to
depend on the LangChain provider packages, keeping this file trivially
unit-testable (backend/tests/unit/test_model_router.py) without a network
connection or API key.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import ModelTier, TaskType

# Tasks that are pure mechanical operations - scaffolding a folder,
# running `npm install`, running a formatter - never need an LLM. Routing
# these to DETERMINISTIC is the single biggest lever in the whole project
# for cutting LLM calls, because it removes entire task categories from
# the token budget rather than making them cheaper.
_DETERMINISTIC_TASK_TYPES = {
    TaskType.SCAFFOLD,
    TaskType.INSTALL_DEPENDENCIES,
    TaskType.FORMAT_LINT,
}

# Default tier for a task type on its FIRST attempt, before any
# escalation logic runs.
_BASE_TIER_BY_TASK_TYPE: dict[TaskType, ModelTier] = {
    TaskType.SCAFFOLD: ModelTier.DETERMINISTIC,
    TaskType.INSTALL_DEPENDENCIES: ModelTier.DETERMINISTIC,
    TaskType.FORMAT_LINT: ModelTier.DETERMINISTIC,
    TaskType.SCHEMA_DESIGN: ModelTier.CODING,
    TaskType.BACKEND_IMPLEMENTATION: ModelTier.CODING,
    TaskType.FRONTEND_IMPLEMENTATION: ModelTier.CODING,
    TaskType.INTEGRATION: ModelTier.CODING,
    TaskType.TEST_AUTHORING: ModelTier.CODING,
    TaskType.BUGFIX: ModelTier.CODING,
    TaskType.DOCUMENTATION: ModelTier.CHEAP,
    TaskType.REVIEW: ModelTier.CHEAP,
}

_ESCALATION_PATH: dict[ModelTier, ModelTier] = {
    ModelTier.CHEAP: ModelTier.CODING,
    ModelTier.CODING: ModelTier.REASONING,
    ModelTier.REASONING: ModelTier.REASONING,  # ceiling - next step is human approval
}

# Planning-phase agent calls (requirement analysis, architecture, task
# decomposition) always use REASONING regardless of task_type, because a
# bad plan is the most expensive possible mistake: every downstream task
# inherits it. This is intentionally the one place the router does not
# try to save tokens - see docs/23-design-decisions.md, "why the planner
# is the one place we don't economize".
PLANNING_TIER = ModelTier.REASONING


@dataclass(frozen=True)
class RoutingDecision:
    tier: ModelTier
    reason: str
    requires_llm: bool
    escalated: bool = False


def base_tier_for_task_type(task_type: TaskType) -> ModelTier:
    return _BASE_TIER_BY_TASK_TYPE.get(task_type, ModelTier.CODING)


def escalate_tier(tier: ModelTier) -> ModelTier:
    return _ESCALATION_PATH.get(tier, ModelTier.REASONING)


def route_task(
    task_type: TaskType,
    attempt_count: int,
    prior_attempt_failed: bool = False,
    force_tier: ModelTier | None = None,
) -> RoutingDecision:
    """The single decision point every task execution goes through.

    Rules (in order):
    1. An explicit force_tier (e.g. a human reviewer overriding routing
       via the approval flow) always wins.
    2. Task types in _DETERMINISTIC_TASK_TYPES never use an LLM - full
       stop, regardless of attempt count.
    3. Otherwise start from the task type's base tier.
    4. If this is a retry after a failure (attempt_count > 1 and the prior
       attempt failed), escalate one tier - a second failure at the same
       tier is evidence the task needs more reasoning, not another
       identical guess.
    """
    if force_tier is not None:
        return RoutingDecision(
            tier=force_tier,
            reason="Tier explicitly forced (human override).",
            requires_llm=force_tier != ModelTier.DETERMINISTIC,
        )

    if task_type in _DETERMINISTIC_TASK_TYPES:
        return RoutingDecision(
            tier=ModelTier.DETERMINISTIC,
            reason=f"Task type '{task_type.value}' is a mechanical operation with no reasoning component.",
            requires_llm=False,
        )

    base = base_tier_for_task_type(task_type)
    if attempt_count > 1 and prior_attempt_failed:
        escalated = escalate_tier(base)
        return RoutingDecision(
            tier=escalated,
            reason=(
                f"Attempt {attempt_count} after a prior failure at '{base.value}' - "
                f"escalating to '{escalated.value}'."
            ),
            requires_llm=True,
            escalated=escalated != base,
        )

    return RoutingDecision(
        tier=base,
        reason=f"Default tier for task type '{task_type.value}'.",
        requires_llm=True,
    )


def route_planning_call(kind: str) -> RoutingDecision:
    return RoutingDecision(
        tier=PLANNING_TIER,
        reason=f"Planning-phase call ('{kind}') always uses the reasoning tier.",
        requires_llm=True,
    )
