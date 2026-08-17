"""Naive-vs-optimized token/cost estimator tests."""
from __future__ import annotations

from app.orchestrator.naive_comparison import NaiveWorkflowAssumptions, compare, estimate_naive_workflow


def test_naive_estimate_grows_with_task_count():
    small = estimate_naive_workflow(task_count=3)
    large = estimate_naive_workflow(task_count=30)
    assert large.llm_calls > small.llm_calls
    assert large.total_tokens > small.total_tokens


def test_naive_input_tokens_grow_faster_than_linearly():
    # This is the specific anti-pattern being modelled: replaying full
    # history means input tokens grow ~quadratically with call count, not
    # linearly - doubling the task count should more than double the
    # naive input token estimate.
    small = estimate_naive_workflow(task_count=5)
    doubled = estimate_naive_workflow(task_count=10)
    ratio_calls = doubled.llm_calls / small.llm_calls
    ratio_tokens = doubled.input_tokens / small.input_tokens
    assert ratio_tokens > ratio_calls


def test_comparison_reports_positive_savings_for_a_realistic_run():
    result = compare(task_count=12, optimized_llm_calls=14, optimized_input_tokens=31420, optimized_output_tokens=8230)
    assert result.tokens_saved > 0
    assert 0 < result.tokens_saved_pct <= 100
    assert result.calls_saved > 0
    assert 0 < result.calls_saved_pct <= 100


def test_comparison_never_reports_negative_savings():
    # Even in a contrived case where "optimized" usage is deliberately
    # made larger than any plausible naive run, savings must clamp to
    # zero rather than go negative and confuse the analytics UI.
    result = compare(task_count=1, optimized_llm_calls=10_000, optimized_input_tokens=10_000_000, optimized_output_tokens=1_000_000)
    assert result.tokens_saved == 0
    assert result.tokens_saved_pct == 0.0
    assert result.calls_saved == 0


def test_assumptions_are_configurable_not_hardcoded():
    custom = NaiveWorkflowAssumptions(calls_per_task=2, planning_calls=1, avg_call_input_base_tokens=100, avg_call_output_tokens=50)
    default_estimate = estimate_naive_workflow(task_count=10)
    custom_estimate = estimate_naive_workflow(task_count=10, assumptions=custom)
    assert custom_estimate.llm_calls < default_estimate.llm_calls
