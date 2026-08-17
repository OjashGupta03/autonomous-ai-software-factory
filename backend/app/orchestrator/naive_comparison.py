"""
Naive-vs-optimized workflow comparison (docs/07-token-optimization.md).

IMPORTANT: `estimate_naive_workflow` is a documented ESTIMATE, not a
measurement. The naive pipeline it describes never actually runs - doing
so would defeat the entire point of this project. The estimate models the
specific anti-pattern this project exists to avoid (see spec section 6):
every task touches every agent (planner/coder/reviewer/tester/debugger),
and each call replays the full conversation history rather than a
task-scoped context, so input tokens grow roughly quadratically with the
number of calls instead of staying flat.

The "actual/optimized" side of the comparison is never estimated - it
comes straight from the recorded `token_usage` rows for the project
(services/token_service.py). Only the naive baseline is synthetic.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NaiveWorkflowAssumptions:
    """Tunable, and deliberately visible as parameters rather than buried
    constants - the frontend's comparison view surfaces these so nobody
    mistakes the naive figure for a measurement. Defaults model the exact
    "Bad architecture" chain from the project brief: Planner -> Task
    Divider -> Backend -> Reviewer -> Tester -> Debugger -> Planner ->
    Reviewer -> ... i.e. roughly 6 agent touches per task."""

    calls_per_task: int = 6
    planning_calls: int = 3  # requirement analysis, architecture, decomposition
    avg_call_input_base_tokens: int = 500
    avg_call_output_tokens: int = 400


@dataclass(frozen=True)
class NaiveEstimate:
    llm_calls: int
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def estimate_naive_workflow(
    task_count: int, assumptions: NaiveWorkflowAssumptions = NaiveWorkflowAssumptions()
) -> NaiveEstimate:
    n = assumptions.planning_calls + task_count * assumptions.calls_per_task
    output_tokens = n * assumptions.avg_call_output_tokens
    # Arithmetic series: call k's input carries the (k-1) prior calls'
    # outputs (full history replay), so total input grows with n^2.
    input_tokens = assumptions.avg_call_input_base_tokens * n + assumptions.avg_call_output_tokens * (
        n * (n - 1) // 2
    )
    return NaiveEstimate(llm_calls=n, input_tokens=input_tokens, output_tokens=output_tokens)


@dataclass(frozen=True)
class ComparisonResult:
    naive: NaiveEstimate
    optimized_llm_calls: int
    optimized_input_tokens: int
    optimized_output_tokens: int

    @property
    def optimized_total_tokens(self) -> int:
        return self.optimized_input_tokens + self.optimized_output_tokens

    @property
    def tokens_saved(self) -> int:
        return max(0, self.naive.total_tokens - self.optimized_total_tokens)

    @property
    def tokens_saved_pct(self) -> float:
        if self.naive.total_tokens == 0:
            return 0.0
        return round(100.0 * self.tokens_saved / self.naive.total_tokens, 1)

    @property
    def calls_saved(self) -> int:
        return max(0, self.naive.llm_calls - self.optimized_llm_calls)

    @property
    def calls_saved_pct(self) -> float:
        if self.naive.llm_calls == 0:
            return 0.0
        return round(100.0 * self.calls_saved / self.naive.llm_calls, 1)


def compare(
    task_count: int,
    optimized_llm_calls: int,
    optimized_input_tokens: int,
    optimized_output_tokens: int,
    assumptions: NaiveWorkflowAssumptions = NaiveWorkflowAssumptions(),
) -> ComparisonResult:
    naive = estimate_naive_workflow(task_count, assumptions)
    return ComparisonResult(
        naive=naive,
        optimized_llm_calls=optimized_llm_calls,
        optimized_input_tokens=optimized_input_tokens,
        optimized_output_tokens=optimized_output_tokens,
    )
