"""Model Router tests (app/orchestrator/model_router.py)."""
from __future__ import annotations

from app.core.constants import ModelTier, TaskType
from app.orchestrator.model_router import (
    escalate_tier,
    route_planning_call,
    route_task,
)


def test_mechanical_task_types_never_require_an_llm():
    for tt in (TaskType.SCAFFOLD, TaskType.INSTALL_DEPENDENCIES, TaskType.FORMAT_LINT):
        decision = route_task(tt, attempt_count=1)
        assert decision.requires_llm is False
        assert decision.tier == ModelTier.DETERMINISTIC


def test_reasoning_heavy_task_types_get_llm_tiers():
    decision = route_task(TaskType.BACKEND_IMPLEMENTATION, attempt_count=1)
    assert decision.requires_llm is True
    assert decision.tier == ModelTier.CODING


def test_documentation_and_review_route_to_cheap_tier():
    for tt in (TaskType.DOCUMENTATION, TaskType.REVIEW):
        decision = route_task(tt, attempt_count=1)
        assert decision.tier == ModelTier.CHEAP


def test_retry_after_failure_escalates_tier():
    first_attempt = route_task(TaskType.BACKEND_IMPLEMENTATION, attempt_count=1)
    retry = route_task(TaskType.BACKEND_IMPLEMENTATION, attempt_count=2, prior_attempt_failed=True)
    assert first_attempt.tier == ModelTier.CODING
    assert retry.tier == ModelTier.REASONING
    assert retry.escalated is True


def test_retry_without_prior_failure_does_not_escalate():
    # attempt_count > 1 alone isn't enough - only an actual prior failure
    # should escalate the tier.
    decision = route_task(TaskType.BACKEND_IMPLEMENTATION, attempt_count=2, prior_attempt_failed=False)
    assert decision.tier == ModelTier.CODING
    assert decision.escalated is False


def test_escalation_path_caps_at_reasoning():
    assert escalate_tier(ModelTier.CHEAP) == ModelTier.CODING
    assert escalate_tier(ModelTier.CODING) == ModelTier.REASONING
    assert escalate_tier(ModelTier.REASONING) == ModelTier.REASONING  # ceiling, not an error


def test_deterministic_task_type_never_escalates_even_after_failure():
    # A "scaffold" task type is deterministic by definition; escalating it
    # after a failure would incorrectly hand a mechanical operation to an
    # LLM, so DETERMINISTIC must win regardless of attempt/failure state.
    decision = route_task(TaskType.SCAFFOLD, attempt_count=3, prior_attempt_failed=True)
    assert decision.tier == ModelTier.DETERMINISTIC
    assert decision.requires_llm is False


def test_force_tier_overrides_everything():
    decision = route_task(TaskType.SCAFFOLD, attempt_count=1, force_tier=ModelTier.REASONING)
    assert decision.tier == ModelTier.REASONING
    assert decision.requires_llm is True


def test_planning_calls_always_use_reasoning_tier():
    for kind in ("requirement_analysis", "architecture_planning", "task_decomposition"):
        decision = route_planning_call(kind)
        assert decision.tier == ModelTier.REASONING
        assert decision.requires_llm is True
