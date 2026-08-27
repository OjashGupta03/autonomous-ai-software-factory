"""
The LangGraph workflow (docs/03-agentic-workflow.md).
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol

from app.orchestrator.state import ProjectGraphState

NodeFn = Callable[[ProjectGraphState], Awaitable[dict[str, Any]]]


class GraphDependencies(Protocol):
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


def route_after_schedule(state: ProjectGraphState) -> str:
    if state.get("batch_ready"):
        return "dispatch_batch"
    if state.get("project_complete"):
        return "run_integration_tests"
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
    """Starts at `schedule_batch` - used when a plan AND a task DAG
    already exist (e.g. resuming after a human approval)."""
    from langgraph.graph import START, StateGraph

    graph = StateGraph(ProjectGraphState)
    _add_execution_nodes(graph, deps)
    graph.add_edge(START, "schedule_batch")
    _add_execution_edges(graph)
    return graph.compile()


def build_decompose_resume_graph(deps: GraphDependencies):
    """FIX (the "Resume Bug"): starts at `decompose_tasks` instead of
    `schedule_batch`.

    Previously `ProjectRunner.run_or_resume` decided fresh-start vs.
    resume purely by checking "does an active ProjectPlan exist?". A
    ProjectPlan is created by `plan_architecture`, which runs BEFORE
    `decompose_tasks`. So if the worker crashed or the Planner's JSON
    could not be parsed during `decompose_tasks` (e.g. malformed JSON
    from the LLM), the project was left with a plan but ZERO tasks. Any
    later resume attempt (a retry, a rerun, an ARQ retry of the crashed
    job) would see "plan exists" and jump straight to `schedule_batch`
    via `build_resume_graph` - which finds zero tasks, immediately
    reports `project_stalled=True`, and routes to `request_human_approval`
    with nothing for a human to actually act on.

    `ProjectRunner.run_or_resume` now also checks whether any Task rows
    exist for the project; if a plan exists but no tasks do, it uses
    THIS graph instead, so decomposition (and only decomposition -
    requirement analysis and architecture do not need to be redone) is
    retried automatically.
    """
    from langgraph.graph import START, StateGraph

    graph = StateGraph(ProjectGraphState)
    graph.add_node("decompose_tasks", deps.decompose_tasks)
    _add_execution_nodes(graph, deps)
    graph.add_edge(START, "decompose_tasks")
    graph.add_edge("decompose_tasks", "schedule_batch")
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

    graph.add_conditional_edges("schedule_batch", route_after_schedule, {
        "dispatch_batch": "dispatch_batch", "run_integration_tests": "run_integration_tests", "request_human_approval": "request_human_approval",
    })
    graph.add_edge("dispatch_batch", "await_batch")
    graph.add_edge("await_batch", "evaluate_batch")

    graph.add_conditional_edges("evaluate_batch", route_after_evaluate, {"handle_failures": "handle_failures", "schedule_batch": "schedule_batch"})
    graph.add_conditional_edges("handle_failures", route_after_handle_failures, {"request_human_approval": "request_human_approval", "schedule_batch": "schedule_batch"})
    graph.add_conditional_edges("run_integration_tests", route_after_tests, {"finalize_project": "finalize_project", "analyze_test_failure": "analyze_test_failure"})
    graph.add_conditional_edges("analyze_test_failure", route_after_test_failure_analysis, {"schedule_batch": "schedule_batch", "request_human_approval": "request_human_approval"})

    graph.add_edge("request_human_approval", END)
    graph.add_edge("finalize_project", END)


GRAPH_NODE_NAMES = [
    "analyze_requirement", "plan_architecture", "decompose_tasks", "schedule_batch", "dispatch_batch",
    "await_batch", "evaluate_batch", "handle_failures", "run_integration_tests", "analyze_test_failure",
    "request_human_approval", "finalize_project",
]
RESUME_GRAPH_NODE_NAMES = [n for n in GRAPH_NODE_NAMES if n not in ("analyze_requirement", "plan_architecture", "decompose_tasks")]
DECOMPOSE_RESUME_GRAPH_NODE_NAMES = [n for n in GRAPH_NODE_NAMES if n not in ("analyze_requirement", "plan_architecture")]
