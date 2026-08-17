# 04 - The Orchestrator

## What "orchestrator" means in this codebase

There is no single class called `Orchestrator`. The orchestrator is a *responsibility*,
split deliberately across three layers so that the decision-making logic never has to be
mixed with I/O:

| Layer | Where | Job |
|---|---|---|
| Graph topology & routing | `app/orchestrator/graph.py` | *What phase comes next*, given the current state. Pure functions - no I/O. |
| Scheduling | `app/orchestrator/scheduler.py` | *Which tasks are unblocked right now*. Pure functions over plain `TaskNode` values - no DB, no LLM. |
| Execution | `app/orchestrator/runner.py` (`ProjectRunner`) | The only layer allowed to touch the database, call an LLM, or enqueue a worker job. Implements the graph's node functions. |

This split is why `graph.py`'s routing functions can be unit tested with zero
mocking (`backend/tests/integration/test_orchestrator_graph.py` passes a stub
`GraphDependencies` and asserts on the call trace) and why `scheduler.py`'s logic can be
tested with zero async/DB setup at all (`backend/tests/unit/test_scheduler.py`).

## Every decision point, and who makes it

| Decision | Made by | Deterministic? |
|---|---|---|
| Does this task need an LLM at all? | `model_router.route_task` | Yes |
| Which model tier for a task that does need one? | `model_router.route_task` | Yes |
| Which tasks are unblocked right now? | `scheduler.get_ready_tasks` | Yes |
| Has the project succeeded / stalled? | `scheduler.is_project_complete` / `is_stalled` | Yes |
| How should a failure be classified? | `failure_recovery.classify_error` | Yes (pattern-matching) |
| Retry, escalate to Debug agent, or ask a human? | `failure_recovery.decide_recovery` | Yes |
| What should the architecture look like? | Planner agent | No (this is the point) |
| How should a specific task be implemented? | Coding/Debug/Tester/Documenter agent | No (this is the point) |

The pattern: **every "should we do X" question is deterministic; every "what should X
contain" question is delegated to an agent.** Scheduling, routing, and recovery are
"should we" questions. Architecture and implementation are "what should" questions.

## The run loop, in prose

`ProjectRunner.run()` compiles the LangGraph app (`build_graph`) and invokes it once. From
there the graph itself loops: `schedule_batch` computes a batch of ready tasks (respecting
`MAX_PARALLEL_TASKS`), `dispatch_batch` enqueues them to ARQ, `await_batch` blocks (via DB
polling, not a fixed sleep) until that specific batch resolves, and `evaluate_batch` +
`handle_failures` decide whether to loop back to `schedule_batch` or escalate. This
continues until the scheduler reports the project complete (routes to integration tests)
or stalled (routes to a human).

`await_batch` polling vs. Redis pub/sub: the orchestration loop's internal wait uses
simple DB polling (~1s interval) rather than subscribing to Redis events, because a missed
pub/sub message here would hang the whole project run, and polling a small `tasks` table
is cheap. The *frontend's* live view, in contrast, uses Redis pub/sub for low-latency
fan-out (see [22 in the original brief -> 16-frontend.md](16-frontend.md)) because a missed
message there just means the UI catches up on the next event, not a stuck orchestrator.

## Resuming after a human decision

`build_resume_graph` (also in `graph.py`) is a second compiled graph that starts at
`schedule_batch` instead of `analyze_requirement` - resuming a project after an approval
must not re-invoke the Planner. `POST /approvals/{id}/decide` enqueues `run_project_job`,
which calls `ProjectRunner.run_or_resume()`; that method checks whether an active
`ProjectPlan` already exists for the project and picks the fresh-start or resume graph
accordingly, deterministically, from Postgres state - never from a guess.
