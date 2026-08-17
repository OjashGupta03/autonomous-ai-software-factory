"""
LangGraph runtime state (docs/09... / docs/03-agentic-workflow.md).

Deliberately minimal. Per the project brief ("store important state in
PostgreSQL, use LangGraph state for runtime workflow state where
appropriate"), `ProjectGraphState` does NOT duplicate the task list, file
contents, or agent outputs - Postgres (via app/models) is the single
source of truth for all of that. The graph state only carries the small
amount of control-flow bookkeeping the conditional-edge routing functions
need: which batch is in flight, whether the scheduler found more work,
whether tests have passed, whether a human needs to step in.

Every orchestrator node that needs task/file/agent data queries the DB
through its injected dependency (see graph.py::GraphDependencies) and
writes back only the routing-relevant verdicts (e.g. `batch_ready`,
`project_complete`) into state. This avoids a second, driftable copy of
the DB living inside the graph run.
"""
from __future__ import annotations

from typing import TypedDict


class ProjectGraphState(TypedDict, total=False):
    project_id: str
    iteration: int

    current_batch_ids: list[str]
    batch_ready: bool
    project_complete: bool
    project_stalled: bool
    batch_had_new_failures: bool

    needs_human: bool
    human_reason: str | None

    test_status: str  # "not_run" | "passed" | "failed"
    integration_test_retry_count: int
    max_integration_test_retries: int

    log: list[str]


def initial_state(project_id: str, max_integration_test_retries: int = 3) -> ProjectGraphState:
    return ProjectGraphState(
        project_id=project_id,
        iteration=0,
        current_batch_ids=[],
        batch_ready=False,
        project_complete=False,
        project_stalled=False,
        batch_had_new_failures=False,
        needs_human=False,
        human_reason=None,
        test_status="not_run",
        integration_test_retry_count=0,
        max_integration_test_retries=max_integration_test_retries,
        log=[],
    )


def log_event(state: ProjectGraphState, message: str) -> list[str]:
    """Helper nodes call to append to the trace without needing to know
    the current log's contents - keeps node bodies short."""
    existing = state.get("log", [])
    return [*existing, message]
