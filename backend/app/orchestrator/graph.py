"""
The LangGraph workflow (docs/03-agentic-workflow.md).

This is intentionally NOT a linear pipeline. `schedule_batch` is
revisited every time a batch of tasks finishes, so the graph loops until
the scheduler reports the project complete or stalled; failures can route
back into scheduling (after a retry/escalation decision) or out to a
human. Every routing function below is plain Python inspecting `state` -
none of them call an LLM to decide "what happens next".

Dependency injection: nodes do not talk to the database, LLMs, or ARQ
directly. `build_graph()` takes a `GraphDependencies` bundle of async
callables and wires each one in as a node. The real implementations
(app/orchestrator/runner.py) do the actual DB/agent/tool work; tests
(backend/tests/integration/test_orchestrator_graph.py) pass a stub bundle
with canned, in-memory responses, so the graph's topology and routing can
be verified without a database, network, or API key.

Version note: this uses the `StateGraph` / `START` / `END` / `add_node` /
`add_edge` / `add_conditional_edges` / `compile()` surface, which has been
stable across LangGraph releases for a long time. It deliberately avoids
newer/more volatile APIs (e.g. the `Send` fan-out primitive, or a specific
checkpointer import path) since real concurrent task execution is
delegated to the ARQ worker pool rather than LangGraph itself - see
docs/17-worker-system.md for why.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol

from app.orchestrator.state import ProjectGraphState

NodeFn = Callable[[ProjectGraphState], Awaitable[dict[str, Any]]]


class GraphDependencies(Protocol):
    """One async method per graph node. See app/orchestrator/runner.py for
    the production implementation and backend/tests/integration/
    test_orchestrator_graph.py for the stub used in tests."""

    analyze_requirement: NodeFn
    plan_architecture: NodeFn
    decompose_tasks: NodeFn
    schedule_batch: NodeFn
    dispatch_batch: NodeFn
    await_batch: NodeFn
    evaluate_batch: NodeFn
    handle_failures: NodeFn
    run_integration_tests: NodeFn
    analyze_test_failure: NodeFn
    request_human_approval: NodeFn
    finalize_project: NodeFn


# --- Routing functions (pure, deterministic, DB-free) ----------------------

def route_after_schedule(state: ProjectGraphState) -> str:
    if state.get("batch_ready"):
        return "dispatch_batch"
    if state.get("project_complete"):
        return "run_integration_tests"
    # Nothing ready and not complete => scheduler found a deadlock
    # (every remaining task is BLOCKED on a failed dependency).
    return "request_human_approval"


def route_after_evaluate(state: ProjectGraphState) -> str:
    if state.get("batch_had_new_failures"):
        return "handle_failures"
    return "schedule_batch"


def route_after_handle_failures(state: ProjectGraphState) -> str:
    if state.get("needs_human"):
        return "request_human_approval"
    return "schedule_batch"


def route_after_tests(state: ProjectGraphState) -> str:
    if state.get("test_status") == "passed":
        return "finalize_project"
    return "analyze_test_failure"


def route_after_test_failure_analysis(state: ProjectGraphState) -> str:
    if state.get("needs_human"):
        return "request_human_approval"
    return "schedule_batch"


def build_graph(deps: GraphDependencies):
    """Returns a compiled LangGraph app. Import of `langgraph` is deferred
    to call time so the rest of this module (routing functions, the
    Protocol) can be imported and unit-tested even in environments where
    langgraph is not installed."""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(ProjectGraphState)

    graph.add_node("analyze_requirement", deps.analyze_requirement)
    graph.add_node("plan_architecture", deps.plan_architecture)
    graph.add_node("decompose_tasks", deps.decompose_tasks)
    _add_execution_nodes(graph, deps)

    graph.add_edge(START, "analyze_requirement")
    graph.add_edge("analyze_requirement", "plan_architecture")
    graph.add_edge("plan_architecture", "decompose_tasks")
    graph.add_edge("decompose_tasks", "schedule_batch")

    _add_execution_edges(graph)

    return graph.compile()


def build_resume_graph(deps: GraphDependencies):
    """A second entry point into the SAME node set, starting at
    `schedule_batch` instead of `analyze_requirement`. Used when
    resuming a project that already has a plan and a task DAG (e.g.
    after a human resolves an approval) - re-running the full graph from
    the top would re-invoke the Planner and create a second, duplicate
    task DAG, which is exactly the kind of redundant LLM usage this
    project exists to avoid. See app/orchestrator/runner.py::run_or_resume
    and docs/13-human-in-the-loop.md."""
    from langgraph.graph import START, StateGraph

    graph = StateGraph(ProjectGraphState)
    _add_execution_nodes(graph, deps)
    graph.add_edge(START, "schedule_batch")
    _add_execution_edges(graph)

    return graph.compile()


def _add_execution_nodes(graph, deps: GraphDependencies) -> None:
    graph.add_node("schedule_batch", deps.schedule_batch)
    graph.add_node("dispatch_batch", deps.dispatch_batch)
    graph.add_node("await_batch", deps.await_batch)
    graph.add_node("evaluate_batch", deps.evaluate_batch)
    graph.add_node("handle_failures", deps.handle_failures)
    graph.add_node("run_integration_tests", deps.run_integration_tests)
    graph.add_node("analyze_test_failure", deps.analyze_test_failure)
    graph.add_node("request_human_approval", deps.request_human_approval)
    graph.add_node("finalize_project", deps.finalize_project)


def _add_execution_edges(graph) -> None:
    from langgraph.graph import END

    graph.add_conditional_edges(
        "schedule_batch",
        route_after_schedule,
        {
            "dispatch_batch": "dispatch_batch",
            "run_integration_tests": "run_integration_tests",
            "request_human_approval": "request_human_approval",
        },
    )
    graph.add_edge("dispatch_batch", "await_batch")
    graph.add_edge("await_batch", "evaluate_batch")

    graph.add_conditional_edges(
        "evaluate_batch",
        route_after_evaluate,
        {"handle_failures": "handle_failures", "schedule_batch": "schedule_batch"},
    )
    graph.add_conditional_edges(
        "handle_failures",
        route_after_handle_failures,
        {"request_human_approval": "request_human_approval", "schedule_batch": "schedule_batch"},
    )
    graph.add_conditional_edges(
        "run_integration_tests",
        route_after_tests,
        {"finalize_project": "finalize_project", "analyze_test_failure": "analyze_test_failure"},
    )
    graph.add_conditional_edges(
        "analyze_test_failure",
        route_after_test_failure_analysis,
        {"schedule_batch": "schedule_batch", "request_human_approval": "request_human_approval"},
    )

    graph.add_edge("request_human_approval", END)
    graph.add_edge("finalize_project", END)


GRAPH_NODE_NAMES = [
    "analyze_requirement",
    "plan_architecture",
    "decompose_tasks",
    "schedule_batch",
    "dispatch_batch",
    "await_batch",
    "evaluate_batch",
    "handle_failures",
    "run_integration_tests",
    "analyze_test_failure",
    "request_human_approval",
    "finalize_project",
]

RESUME_GRAPH_NODE_NAMES = [n for n in GRAPH_NODE_NAMES if n not in ("analyze_requirement", "plan_architecture", "decompose_tasks")]
