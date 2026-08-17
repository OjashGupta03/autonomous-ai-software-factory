"""
End-to-end tests of the compiled LangGraph workflow (app/orchestrator/graph.py),
using a stub `GraphDependencies` implementation instead of real DB/LLM/ARQ
calls. This is what actually proves the graph's node wiring and
conditional routing behave correctly as a whole, not just that each
routing function is individually correct (see
backend/tests/unit/test_scheduler.py etc. for the unit-level coverage).

These four scenarios were hand-verified during development against a
throwaway fake-langgraph shim (this sandbox could not install the real
`langgraph` package - see docs/20-local-development.md); this file runs
the same scenarios against the REAL compiled graph and is the version
that should actually be trusted.
"""
from __future__ import annotations

import pytest

from app.orchestrator.graph import build_graph, build_resume_graph
from app.orchestrator.state import initial_state


class _HappyPathDeps:
    """3 tasks, 2 dispatch rounds, tests pass on the first try."""

    def __init__(self):
        self.tasks = {"T1": "pending", "T2": "pending", "T3": "pending"}
        self.calls: list[str] = []

    async def analyze_requirement(self, state):
        self.calls.append("analyze_requirement")
        return {}

    async def plan_architecture(self, state):
        self.calls.append("plan_architecture")
        return {}

    async def decompose_tasks(self, state):
        self.calls.append("decompose_tasks")
        return {}

    async def schedule_batch(self, state):
        self.calls.append("schedule_batch")
        ready = [t for t, s in self.tasks.items() if s == "pending"][:2]
        complete = all(s == "completed" for s in self.tasks.values())
        return {"current_batch_ids": ready, "batch_ready": len(ready) > 0, "project_complete": complete, "project_stalled": False}

    async def dispatch_batch(self, state):
        self.calls.append("dispatch_batch")
        for t in state["current_batch_ids"]:
            self.tasks[t] = "running"
        return {}

    async def await_batch(self, state):
        self.calls.append("await_batch")
        for t in state["current_batch_ids"]:
            self.tasks[t] = "completed"
        return {}

    async def evaluate_batch(self, state):
        self.calls.append("evaluate_batch")
        return {"batch_had_new_failures": False}

    async def handle_failures(self, state):
        raise AssertionError("must not be reached on the happy path")

    async def run_integration_tests(self, state):
        self.calls.append("run_integration_tests")
        return {"test_status": "passed"}

    async def analyze_test_failure(self, state):
        raise AssertionError("must not be reached on the happy path")

    async def request_human_approval(self, state):
        raise AssertionError("must not be reached on the happy path")

    async def finalize_project(self, state):
        self.calls.append("finalize_project")
        return {}


@pytest.mark.asyncio
async def test_happy_path_reaches_finalize_with_multiple_scheduling_rounds():
    deps = _HappyPathDeps()
    app = build_graph(deps)
    final_state = await app.ainvoke(initial_state("proj-a"), config={"recursion_limit": 100})

    assert deps.calls[0] == "analyze_requirement"
    assert deps.calls[-1] == "finalize_project"
    # 2 dispatch rounds (T1+T2, then T3), plus one more schedule_batch
    # call that correctly detects "nothing left ready AND complete" and
    # routes onward to integration tests.
    assert deps.calls.count("schedule_batch") == 3
    assert deps.calls.count("dispatch_batch") == 2
    assert deps.calls.count("run_integration_tests") == 1
    assert all(s == "completed" for s in deps.tasks.values())
    assert final_state["test_status"] == "passed"


class _RetryThenSucceedDeps:
    """A task fails once and is retried via handle_failures; integration
    tests fail once and are retried via analyze_test_failure."""

    def __init__(self):
        self.tasks = {"T1": "pending"}
        self.attempts = {"T1": 0}
        self.calls: list[str] = []
        self.test_run_count = 0

    async def analyze_requirement(self, state):
        return {}

    async def plan_architecture(self, state):
        return {}

    async def decompose_tasks(self, state):
        return {}

    async def schedule_batch(self, state):
        self.calls.append("schedule_batch")
        ready = [t for t, s in self.tasks.items() if s == "pending"]
        complete = all(s == "completed" for s in self.tasks.values())
        return {"current_batch_ids": ready, "batch_ready": len(ready) > 0, "project_complete": complete, "project_stalled": False}

    async def dispatch_batch(self, state):
        for t in state["current_batch_ids"]:
            self.tasks[t] = "running"
            self.attempts[t] += 1
        return {}

    async def await_batch(self, state):
        for t in state["current_batch_ids"]:
            self.tasks[t] = "failed" if self.attempts[t] == 1 else "completed"
        return {}

    async def evaluate_batch(self, state):
        return {"batch_had_new_failures": any(s == "failed" for s in self.tasks.values())}

    async def handle_failures(self, state):
        self.calls.append("handle_failures")
        for t, s in list(self.tasks.items()):
            if s == "failed":
                self.tasks[t] = "pending"
        return {"needs_human": False}

    async def run_integration_tests(self, state):
        self.calls.append("run_integration_tests")
        self.test_run_count += 1
        return {"test_status": "passed" if self.test_run_count >= 2 else "failed"}

    async def analyze_test_failure(self, state):
        self.calls.append("analyze_test_failure")
        return {"needs_human": False, "integration_test_retry_count": state.get("integration_test_retry_count", 0) + 1}

    async def request_human_approval(self, state):
        raise AssertionError("must not be reached in this scenario")

    async def finalize_project(self, state):
        self.calls.append("finalize_project")
        return {}


@pytest.mark.asyncio
async def test_task_retry_and_test_retry_loops_both_recover():
    deps = _RetryThenSucceedDeps()
    app = build_graph(deps)
    final_state = await app.ainvoke(initial_state("proj-b"), config={"recursion_limit": 100})

    assert "handle_failures" in deps.calls
    assert deps.calls.count("run_integration_tests") == 2
    assert deps.calls.count("analyze_test_failure") == 1
    assert deps.calls[-1] == "finalize_project"
    assert final_state["test_status"] == "passed"


class _AlwaysFailsDeps:
    """A task fails past its retry budget -> must stop at human approval,
    and must NEVER reach finalize_project."""

    async def analyze_requirement(self, state):
        return {}

    async def plan_architecture(self, state):
        return {}

    async def decompose_tasks(self, state):
        return {}

    async def schedule_batch(self, state):
        return {"current_batch_ids": ["T1"], "batch_ready": True, "project_complete": False, "project_stalled": False}

    async def dispatch_batch(self, state):
        return {}

    async def await_batch(self, state):
        return {}

    async def evaluate_batch(self, state):
        return {"batch_had_new_failures": True}

    async def handle_failures(self, state):
        return {"needs_human": True, "human_reason": "max retries exceeded"}

    async def run_integration_tests(self, state):
        raise AssertionError("must not be reached")

    async def analyze_test_failure(self, state):
        raise AssertionError("must not be reached")

    async def request_human_approval(self, state):
        return {}

    async def finalize_project(self, state):
        raise AssertionError("a project stuck needing human approval must never auto-finalize")


@pytest.mark.asyncio
async def test_repeated_failure_stops_at_human_approval_not_finalize():
    app = build_graph(_AlwaysFailsDeps())
    final_state = await app.ainvoke(initial_state("proj-c"), config={"recursion_limit": 100})
    assert final_state["needs_human"] is True


@pytest.mark.asyncio
async def test_resume_graph_skips_planning_entirely():
    calls: list[str] = []

    async def unreachable(state):
        raise AssertionError("resume graph must never call planning nodes")

    class _ResumeDeps:
        pass

    deps = _ResumeDeps()
    deps.analyze_requirement = unreachable
    deps.plan_architecture = unreachable
    deps.decompose_tasks = unreachable
    deps.dispatch_batch = unreachable
    deps.await_batch = unreachable
    deps.evaluate_batch = unreachable
    deps.handle_failures = unreachable
    deps.analyze_test_failure = unreachable
    deps.request_human_approval = unreachable

    async def schedule_batch(state):
        calls.append("schedule_batch")
        return {"current_batch_ids": [], "batch_ready": False, "project_complete": True, "project_stalled": False}

    async def run_integration_tests(state):
        calls.append("run_integration_tests")
        return {"test_status": "passed"}

    async def finalize_project(state):
        calls.append("finalize_project")
        return {}

    deps.schedule_batch = schedule_batch
    deps.run_integration_tests = run_integration_tests
    deps.finalize_project = finalize_project

    app = build_resume_graph(deps)
    await app.ainvoke(initial_state("proj-d"), config={"recursion_limit": 100})
    assert calls == ["schedule_batch", "run_integration_tests", "finalize_project"]
