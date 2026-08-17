"""
Scheduler tests (app/orchestrator/scheduler.py). Pure-Python, zero DB/LLM
- these should be fast and need nothing beyond pytest.
"""
from __future__ import annotations

import pytest

from app.core.constants import TaskStatus
from app.orchestrator.scheduler import (
    CyclicDependencyError,
    TaskNode,
    get_newly_blocked_tasks,
    get_ready_tasks,
    is_project_complete,
    is_stalled,
    topological_order,
    validate_dag,
)


def test_topological_order_simple_chain():
    tasks = [
        TaskNode(id="T1", status=TaskStatus.PENDING, depends_on=()),
        TaskNode(id="T2", status=TaskStatus.PENDING, depends_on=("T1",)),
        TaskNode(id="T3", status=TaskStatus.PENDING, depends_on=("T2",)),
    ]
    assert topological_order(tasks) == ["T1", "T2", "T3"]


def test_topological_order_diamond():
    tasks = [
        TaskNode(id="T1", status=TaskStatus.PENDING, depends_on=()),
        TaskNode(id="T2", status=TaskStatus.PENDING, depends_on=("T1",)),
        TaskNode(id="T3", status=TaskStatus.PENDING, depends_on=("T1",)),
        TaskNode(id="T4", status=TaskStatus.PENDING, depends_on=("T2", "T3")),
    ]
    order = topological_order(tasks)
    assert order.index("T1") < order.index("T2")
    assert order.index("T1") < order.index("T3")
    assert order.index("T2") < order.index("T4")
    assert order.index("T3") < order.index("T4")


def test_cycle_detection():
    tasks = [
        TaskNode(id="A", status=TaskStatus.PENDING, depends_on=("B",)),
        TaskNode(id="B", status=TaskStatus.PENDING, depends_on=("C",)),
        TaskNode(id="C", status=TaskStatus.PENDING, depends_on=("A",)),
    ]
    with pytest.raises(CyclicDependencyError):
        topological_order(tasks)


def test_validate_dag_rejects_unknown_dependency():
    tasks = [TaskNode(id="A", status=TaskStatus.PENDING, depends_on=("does-not-exist",))]
    with pytest.raises(ValueError):
        validate_dag(tasks)


def test_ready_tasks_respects_dependencies():
    tasks = [
        TaskNode(id="T1", status=TaskStatus.COMPLETED, depends_on=()),
        TaskNode(id="T2", status=TaskStatus.PENDING, depends_on=("T1",)),
        TaskNode(id="T3", status=TaskStatus.PENDING, depends_on=("T2",)),  # not ready yet
    ]
    ready = get_ready_tasks(tasks, running_count=0, max_parallel=10)
    assert ready == ["T2"]


def test_ready_tasks_respects_parallelism_cap():
    tasks = [
        TaskNode(id="T1", status=TaskStatus.PENDING, depends_on=()),
        TaskNode(id="T2", status=TaskStatus.PENDING, depends_on=()),
        TaskNode(id="T3", status=TaskStatus.PENDING, depends_on=()),
    ]
    ready = get_ready_tasks(tasks, running_count=0, max_parallel=2)
    assert len(ready) == 2

    ready_when_one_already_running = get_ready_tasks(tasks, running_count=1, max_parallel=2)
    assert len(ready_when_one_already_running) == 1


def test_ready_tasks_priority_ordering():
    tasks = [
        TaskNode(id="low", status=TaskStatus.PENDING, depends_on=(), priority=0),
        TaskNode(id="high", status=TaskStatus.PENDING, depends_on=(), priority=100),
    ]
    ready = get_ready_tasks(tasks, running_count=0, max_parallel=1)
    assert ready == ["high"]


def test_newly_blocked_propagates_from_failed_dependency():
    tasks = [
        TaskNode(id="T1", status=TaskStatus.FAILED, depends_on=()),
        TaskNode(id="T2", status=TaskStatus.PENDING, depends_on=("T1",)),
        TaskNode(id="T3", status=TaskStatus.PENDING, depends_on=()),  # unaffected
    ]
    assert get_newly_blocked_tasks(tasks) == ["T2"]


def test_project_complete_requires_all_terminal():
    incomplete = [TaskNode(id="T1", status=TaskStatus.COMPLETED), TaskNode(id="T2", status=TaskStatus.PENDING)]
    assert is_project_complete(incomplete) is False

    complete = [TaskNode(id="T1", status=TaskStatus.COMPLETED), TaskNode(id="T2", status=TaskStatus.SKIPPED)]
    assert is_project_complete(complete) is True


def test_project_complete_is_false_when_a_task_failed_or_is_blocked():
    # Regression test: a project where every task has REACHED a terminal
    # status (nothing left to schedule) is not the same thing as a
    # project that SUCCEEDED. A FAILED or BLOCKED task must make
    # is_project_complete() return False, even though no more scheduling
    # is possible - otherwise the orchestrator would route a broken build
    # straight into "run the tests" as if nothing were wrong, instead of
    # to human escalation via is_stalled().
    failed_present = [TaskNode(id="T1", status=TaskStatus.FAILED), TaskNode(id="T2", status=TaskStatus.COMPLETED)]
    assert is_project_complete(failed_present) is False

    blocked_present = [TaskNode(id="T1", status=TaskStatus.FAILED), TaskNode(id="T2", status=TaskStatus.BLOCKED, depends_on=("T1",))]
    assert is_project_complete(blocked_present) is False


def test_project_complete_false_for_empty_task_list():
    # An empty task list is "nothing to schedule yet", not "done" -
    # otherwise a project between decompose_tasks and its first
    # schedule_batch call would be misreported as already complete.
    assert is_project_complete([]) is False


def test_is_stalled_detects_deadlock():
    tasks = [
        TaskNode(id="T1", status=TaskStatus.FAILED, depends_on=()),
        TaskNode(id="T2", status=TaskStatus.BLOCKED, depends_on=("T1",)),
    ]
    assert is_stalled(tasks, running_count=0) is True


def test_is_stalled_false_while_tasks_are_running():
    tasks = [TaskNode(id="T1", status=TaskStatus.RUNNING, depends_on=())]
    assert is_stalled(tasks, running_count=1) is False
