"""
Deterministic task-DAG scheduler.

This module contains ZERO calls to an LLM and ZERO calls to the database.
It operates purely on lightweight `TaskNode` value objects so it can be
unit tested in isolation (see backend/tests/unit/test_scheduler.py) and so
the orchestrator's "what should happen next" logic is never accidentally
entangled with I/O.

Why deterministic: scheduling ("which tasks are unblocked right now") is a
graph-reachability problem, not a reasoning problem. Spending an LLM call
to answer it would be exactly the anti-pattern the project exists to avoid
(see docs/04-orchestrator.md and docs/23-design-decisions.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.constants import TaskStatus

TERMINAL_FAILURE_STATUSES = {TaskStatus.FAILED}
TERMINAL_SUCCESS_STATUSES = {TaskStatus.COMPLETED, TaskStatus.SKIPPED}
TERMINAL_STATUSES = TERMINAL_FAILURE_STATUSES | TERMINAL_SUCCESS_STATUSES
ACTIVE_STATUSES = {TaskStatus.RUNNING, TaskStatus.NEEDS_APPROVAL}


class CyclicDependencyError(ValueError):
    """Raised when the task graph submitted by the Planner is not a DAG.
    This is caught by the decompose_tasks node, which asks the Planner to
    re-propose the graph rather than silently dropping the cycle."""


@dataclass(frozen=True)
class TaskNode:
    id: str
    status: TaskStatus
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    priority: int = 0


def build_dependency_map(tasks: list[TaskNode]) -> dict[str, set[str]]:
    return {t.id: set(t.depends_on) for t in tasks}


def topological_order(tasks: list[TaskNode]) -> list[str]:
    """Kahn's algorithm. Raises CyclicDependencyError if the graph the
    Planner produced is not acyclic. O(V+E)."""
    dep_map = build_dependency_map(tasks)
    ids = list(dep_map.keys())
    known = set(ids)

    # in_degree counts only edges whose source we actually know about, so a
    # dangling dependency (typo'd id) doesn't silently break the count.
    in_degree = {i: 0 for i in ids}
    dependents: dict[str, list[str]] = {i: [] for i in ids}
    for task_id, deps in dep_map.items():
        for dep in deps:
            if dep not in known:
                continue
            in_degree[task_id] += 1
            dependents[dep].append(task_id)

    queue = sorted([i for i in ids if in_degree[i] == 0])
    order: list[str] = []
    while queue:
        queue.sort()
        current = queue.pop(0)
        order.append(current)
        for nxt in dependents[current]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    if len(order) != len(ids):
        remaining = known - set(order)
        raise CyclicDependencyError(
            f"Task graph contains a cycle involving: {sorted(remaining)}"
        )
    return order


def validate_dag(tasks: list[TaskNode]) -> None:
    """Raises CyclicDependencyError on a bad graph; also raises ValueError
    if a task depends on an id that doesn't exist in the batch at all
    (as opposed to existing-but-unknown-to-this-function, which
    topological_order tolerates for partial-batch calls)."""
    ids = {t.id for t in tasks}
    for t in tasks:
        for dep in t.depends_on:
            if dep not in ids:
                raise ValueError(f"Task {t.id} depends on unknown task {dep}")
    topological_order(tasks)


def dependencies_satisfied(task: TaskNode, status_by_id: dict[str, TaskStatus]) -> bool:
    return all(status_by_id.get(dep) in TERMINAL_SUCCESS_STATUSES for dep in task.depends_on)


def dependencies_permanently_blocked(task: TaskNode, status_by_id: dict[str, TaskStatus]) -> bool:
    return any(status_by_id.get(dep) in TERMINAL_FAILURE_STATUSES for dep in task.depends_on)


def get_ready_tasks(
    tasks: list[TaskNode],
    running_count: int,
    max_parallel: int,
) -> list[str]:
    """Returns task ids that are unblocked and can be dispatched right
    now, ordered by (priority desc, id asc) for determinism, capped so
    total in-flight work never exceeds `max_parallel`.
    """
    status_by_id = {t.id: t.status for t in tasks}
    capacity = max(0, max_parallel - running_count)
    if capacity == 0:
        return []

    candidates = [
        t
        for t in tasks
        if t.status in (TaskStatus.PENDING, TaskStatus.READY)
        and dependencies_satisfied(t, status_by_id)
    ]
    candidates.sort(key=lambda t: (-t.priority, t.id))
    return [t.id for t in candidates[:capacity]]


def get_newly_blocked_tasks(tasks: list[TaskNode]) -> list[str]:
    """Tasks whose upstream dependency has permanently failed (and who are
    not already terminal themselves) should transition to BLOCKED so the
    UI stops showing them as pending-forever."""
    status_by_id = {t.id: t.status for t in tasks}
    blocked = []
    for t in tasks:
        if t.status in TERMINAL_STATUSES or t.status == TaskStatus.BLOCKED:
            continue
        if dependencies_permanently_blocked(t, status_by_id):
            blocked.append(t.id)
    return blocked


def is_project_complete(tasks: list[TaskNode]) -> bool:
    """True ONLY when every task succeeded (COMPLETED or SKIPPED) - i.e.
    the build phase is genuinely done and it is safe to proceed to
    integration testing. A FAILED or BLOCKED task means the project has
    stopped making progress but did NOT complete successfully - that
    case is is_stalled()'s job to report, not this function's. Conflating
    the two would route a project with a dead task straight into
    "run the tests" as if nothing were wrong."""
    if not tasks:
        return False
    return all(t.status in TERMINAL_SUCCESS_STATUSES for t in tasks)


def has_unrecoverable_failure(tasks: list[TaskNode]) -> bool:
    return any(t.status == TaskStatus.FAILED for t in tasks)


def is_stalled(tasks: list[TaskNode], running_count: int) -> bool:
    """True if nothing is running, nothing is ready, and the project did
    NOT complete successfully - i.e. at least one task is FAILED or
    BLOCKED and nothing can make further progress without intervention.
    This is a deadlock signal, not a bug: it means upstream failures have
    and the runner should route to human escalation."""
    if not tasks:
        return False
    if is_project_complete(tasks):
        return False
    if running_count > 0:
        return False
    ready = get_ready_tasks(tasks, running_count=0, max_parallel=len(tasks) or 1)
    return len(ready) == 0
