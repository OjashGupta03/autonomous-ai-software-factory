from __future__ import annotations
import pytest
from app.orchestrator.graph import build_graph, build_resume_graph, build_decompose_resume_graph
from app.orchestrator.state import initial_state


class _HappyPathDeps:
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
    assert deps.calls.count("schedule_batch") == 3
    assert deps.calls.count("dispatch_batch") == 2
    assert final_state["test_status"] == "passed"


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


@pytest.mark.asyncio
async def test_decompose_resume_graph_redoes_decomposition_but_not_planning():
    """Regression test for the graph half of the Resume Bug fix: this
    entry point must call decompose_tasks (recovering from a crash mid-
    decomposition) but must NEVER call analyze_requirement/plan_architecture
    again."""
    calls: list[str] = []

    async def unreachable(state):
        raise AssertionError("decompose-resume graph must never re-run planning nodes")

    class _Deps:
        pass

    deps = _Deps()
    deps.analyze_requirement = unreachable
    deps.plan_architecture = unreachable
    deps.dispatch_batch = unreachable
    deps.await_batch = unreachable
    deps.evaluate_batch = unreachable
    deps.handle_failures = unreachable
    deps.analyze_test_failure = unreachable
    deps.request_human_approval = unreachable

    async def decompose_tasks(state):
        calls.append("decompose_tasks")
        return {}

    async def schedule_batch(state):
        calls.append("schedule_batch")
        return {"current_batch_ids": [], "batch_ready": False, "project_complete": True, "project_stalled": False}

    async def run_integration_tests(state):
        calls.append("run_integration_tests")
        return {"test_status": "passed"}

    async def finalize_project(state):
        calls.append("finalize_project")
        return {}

    deps.decompose_tasks = decompose_tasks
    deps.schedule_batch = schedule_batch
    deps.run_integration_tests = run_integration_tests
    deps.finalize_project = finalize_project

    app = build_decompose_resume_graph(deps)
    await app.ainvoke(initial_state("proj-e"), config={"recursion_limit": 100})
    assert calls == ["decompose_tasks", "schedule_batch", "run_integration_tests", "finalize_project"]
