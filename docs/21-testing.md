# 21 - Testing

## What exists

| File | Covers |
|---|---|
| `tests/unit/test_scheduler.py` | DAG topological order, cycle detection, ready-task selection, parallelism cap, priority ordering, blocked-propagation, the complete-vs-stalled distinction (with a regression test - see [05-task-dag.md](05-task-dag.md)) |
| `tests/unit/test_context_manager.py` | Budget respected at generous/tiny/zero budgets, task description never dropped, no unrelated content leaks in |
| `tests/unit/test_model_router.py` | Deterministic task types never route to an LLM, retry-after-failure escalates tiers, deterministic types never escalate, planning calls always use REASONING |
| `tests/unit/test_failure_recovery.py` | Error classification patterns, transient-vs-code-level retry policy, max-attempts forces human approval, exponential backoff shape |
| `tests/unit/test_naive_comparison.py` | Naive estimate grows faster than linearly, savings never negative |
| `tests/unit/test_agent_loop.py` | Zero/one/many tool calls, iteration cap enforced, a raising tool doesn't crash the loop, an unknown tool name is handled |
| `tests/unit/test_pricing.py` | Cost calculation, unknown-model fallback |
| `tests/integration/test_orchestrator_graph.py` | The full compiled LangGraph app, stub dependencies: happy path (multiple scheduling rounds), task-retry + test-retry loops both recovering, repeated failure stopping at human approval (never auto-finalizing), the resume graph skipping planning entirely |
| `tests/integration/test_api_auth.py` | Register/login/me, duplicate registration rejected, wrong password rejected, protected routes require a token |
| `tests/integration/test_api_projects.py` | Create/list/get, cross-user isolation (404, not 403) |
| `tests/integration/test_task_and_approval_flow.py` | Task graph API reflects seeded dependencies, approval list/decide flow, fresh-project metrics report zero |

`tests/conftest.py` runs every integration test against an in-memory SQLite database
(shared connection via `StaticPool`, `get_db` overridden via FastAPI's
`dependency_overrides`) rather than a live Postgres instance - this is what
`app/db/types.py::GUID` (see [14-database-design.md](14-database-design.md)) exists to
make possible.

## What was actually run, and what wasn't - stated precisely

The sandbox that built this repository had **no network access and no installable Python
or Node packages** (confirmed: `pip install` and `npm install` both fail against a blocked
registry). This is a hard constraint on what could be *executed* versus *written*:

**Actually executed and passing**, using only the Python standard library plus two small,
throwaway compatibility shims (a stand-in for the ~40-line slice of `pytest` this suite's
assertions need, and a stand-in implementing the same `StateGraph`/`add_node`/
`add_conditional_edges`/`compile`/`ainvoke` surface the real `langgraph` package
exposes - neither shim ships in this repository):

- All 49 unit tests (scheduler, context manager, model router, failure recovery, naive
  comparison, agent loop, pricing).
- All 4 integration scenarios in `test_orchestrator_graph.py`, against the actual,
  unmodified `app/orchestrator/graph.py`.
- Every backend `.py` file (107 files) compiles cleanly (`py_compile`).
- Every backend `from app.X import Y` statement resolves to a real module and, on a
  best-effort basis, a real name in it (a custom AST-based checker, not just `py_compile`).

This process found and fixed three real bugs before they shipped:
1. `context_manager.build_task_context` silently ignored a caller's token budget below a
   ~256-token floor (see [06-context-engineering.md](06-context-engineering.md)).
2. `tools/base.py`'s `timed()` helper raised `KeyError` on any tool's early-return-inside-
   the-`with`-block path (see [10-tool-system.md](10-tool-system.md)).
3. `scheduler.is_project_complete` treated a failed/blocked project as "complete" (see
   [05-task-dag.md](05-task-dag.md)) - the kind of bug that only surfaces when the
   scheduling logic actually runs against an adversarial state, which is precisely why
   this suite exists.

**Written but not executed** (needs a real network connection and/or a real Docker
daemon, neither available while building this repo):
- `pytest` itself was never run (it isn't installed) - the "49 passed" above comes from a
  bespoke, honest-effort test collector/runner, not from `pytest`'s own reporting.
- `test_api_auth.py`, `test_api_projects.py`, `test_task_and_approval_flow.py` need
  `fastapi`, `sqlalchemy`, and `httpx` installed - none were available.
- Anything touching a real LLM provider, real Postgres, or the Docker sandbox executor.
- The entire frontend test suite (`vitest`) and `npm run build`.

Running `pip install -r backend/requirements-dev.txt && pytest backend/tests -q` is the
single highest-value thing to do first in a real environment - see
[20-local-development.md](20-local-development.md).

## Frontend

`vitest` + React Testing Library. `StatusBadge.test.tsx` (label rendering, unknown-status
fallback, color class selection) and `layout.test.ts` (dependency-depth graph layout:
ordering, same-depth grouping, empty input, cycle-safety). Not executed - see
[16-frontend.md](16-frontend.md).
