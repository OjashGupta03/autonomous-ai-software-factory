# 23 - Design Decisions

This is the single place every "why did you choose X" question is answered directly.
Most decisions have a full treatment elsewhere; this page gives the short answer and
points to it, and covers a handful of decisions that don't have a natural home elsewhere.

## Why LangGraph?

Because the workflow is genuinely a graph, not a pipeline: `schedule_batch` is revisited
an unknown number of times, failures route back into scheduling instead of falling
through a fixed sequence, and the integration-test-retry path shares the scheduling loop
rather than duplicating it. LangGraph's `StateGraph` (nodes + plain edges + conditional
edges) is a direct fit for expressing that without hand-rolling a state machine. The
project deliberately uses only its long-stable core surface
(`add_node`/`add_edge`/`add_conditional_edges`/`compile()`/`START`/`END`) rather than
newer, more volatile parts of the API (checkpointers, the `Send` fan-out primitive) - see
[03-agentic-workflow.md](03-agentic-workflow.md) and
[17-worker-system.md](17-worker-system.md#why-langgraph-doesnt-do-this-fan-out-itself)
for why concurrent task execution is delegated to ARQ instead of expressed as LangGraph
fan-out.

## Why LangChain?

As the provider abstraction, and nothing more. `app/orchestrator/llm_clients.py` is the
only file that imports `langchain_openai`/`langchain_anthropic`; the rest of the codebase
talks to a five-method `LLMClient` interface. This buys tool-calling message plumbing
(`bind_tools`, structured `tool_calls` on a response) that would otherwise be
reimplemented per provider, without coupling the agent loop
(`app/agents/base.py`) to any specific vendor SDK.

## Why PostgreSQL?

Relational integrity actually matters here: task dependencies are foreign keys, token
usage rows reference specific tasks and agent runs, and the analytics queries
([15-api.md](15-api.md)) are genuine joins/aggregations, not document lookups. `asyncpg`
gives a mature async driver matching the rest of the stack. Tests run against SQLite
instead (see [14-database-design.md](14-database-design.md#cross-dialect-uuids)) - a
pragmatic choice for a fast, dependency-free test suite, not a statement that SQLite is
suitable in production for this schema.

## Why Redis (and why not Kafka)?

Full treatment: [17-worker-system.md](17-worker-system.md). Short version: Redis backs
three real, modest-throughput needs (job queue, pub/sub event fan-out, an LLM-cache key
space) that don't individually or collectively justify a second stateful system. Kafka
earns its complexity at durable-replayable-log-with-multiple-independent-consumer-groups
scale; nothing here operates at that scale or needs that consumption model.

## Why ARQ over Celery/Dramatiq?

Full treatment: [17-worker-system.md](17-worker-system.md#the-decision-arq-not-celery-not-kafka-not-dramatiq).
Short version: the codebase is async end to end; ARQ's job functions are `async def`
natively, Celery's execution model is not.

## Why structured state (not conversation replay)?

Because conversation replay is the specific anti-pattern this project exists to avoid -
input tokens growing with the square of the call count as every call re-sends
everything that came before (modeled explicitly in
[07-token-optimization.md](07-token-optimization.md)'s naive-workflow estimator).
Postgres is the durable source of truth; `ProjectGraphState` (see
[04-orchestrator.md](04-orchestrator.md)) carries only the small amount of routing-
relevant bookkeeping the graph's conditional edges need, and is reconstructed fresh
(`initial_state`) per orchestrator invocation rather than accumulated indefinitely.

## Why a task DAG?

Because "implement the backend" and "implement the frontend" are usually independent of
each other but both depend on "design the schema" - modeling this explicitly is what lets
`scheduler.get_ready_tasks` dispatch real parallel work instead of a strictly sequential
task list. See [05-task-dag.md](05-task-dag.md).

## Why model routing?

Because "which model" and "how much context" are the two levers that actually move token
cost, and neither should be a single global choice. See
[08-model-routing.md](08-model-routing.md). The one deliberate exception - the Planner
always uses the top tier - is explained there too: a cheap plan that's wrong costs far
more in downstream retries than a well-reasoned plan costs upfront.

## Why context minimization?

Full treatment: [06-context-engineering.md](06-context-engineering.md). Short version:
most of what a naive implementation would include in an agent's context is irrelevant to
its specific task, and irrelevant context is pure cost with no accuracy benefit.

## Why deterministic tools (and deterministic scheduling/routing/recovery)?

Because "is this task mechanical" and "are this task's dependencies satisfied" and "has
this task failed enough times to need a human" are all questions with a computable right
answer - spending an LLM call to answer any of them would be the exact anti-pattern the
project brief warns against (the "Bad architecture" diagram in section 6 of the brief).
Every deterministic module in `app/orchestrator/` (`scheduler.py`, `model_router.py`,
`failure_recovery.py`, `context_manager.py`, `naive_comparison.py`) is plain Python with
no LLM/DB/network dependency specifically so this property is enforceable and testable,
not just claimed - see [21-testing.md](21-testing.md).

## Why sandboxed execution?

Because this system executes LLM-generated code, which is a different trust boundary than
code a human wrote and reviewed, full stop. See
[11-code-execution-sandbox.md](11-code-execution-sandbox.md) for the mechanism and its
honestly-stated limitations.

## Why human approval checkpoints?

Because some failure modes (a task that's failed 3 times, a project with no forward
progress possible) should stop autonomous execution rather than keep guessing, and some
categories of action (the schema also supports destructive DB changes, external
deployment, high-cost escalation) are inherently the kind of decision a human should make
even if the system *could* keep going. See
[13-human-in-the-loop.md](13-human-in-the-loop.md).

## Smaller decisions worth explaining

**Why no separate `model_usage` table, and why "git diff" isn't backed by git.** Both are
consolidations from the project brief's original 20-table list down to 18, covered in
[14-database-design.md](14-database-design.md) and [10-tool-system.md](10-tool-system.md)
respectively - in both cases, the "missing" piece is a query/computation over data that's
already fully captured elsewhere, not a dropped requirement.

**Why the initial Alembic migration calls `Base.metadata.create_all()` instead of
hand-written `op.create_table()` calls.** No live Postgres connection was available to run
`alembic revision --autogenerate` while building this repository. Hand-transcribing ~150
columns across 18 tables by reading the model files is exactly the kind of mechanical work
that silently drifts from the source of truth; generating DDL from the same
`Base.metadata` the application already imports cannot drift from it by construction. See
[14-database-design.md](14-database-design.md).

**Why `/auth/login` uses an OAuth2 password form instead of a JSON body.** So FastAPI's
generated `/docs` "Authorize" button works without extra configuration, and so the
`tokenUrl` already declared in `api/deps.py::oauth2_scheme` is actually accurate. This
was, in fact, fixed partway through building this repository - see
[21-testing.md](21-testing.md) for the audit process that caught it.

**Why SQLite for tests, and what `app/db/types.py::GUID` is for.** A test suite that needs
a live Postgres instance is a test suite fewer people actually run. The `GUID`
`TypeDecorator` (native `UUID` on Postgres, `CHAR(32)` on SQLite) is what makes every
model usable against both without maintaining two parallel schemas. See
[14-database-design.md](14-database-design.md#cross-dialect-uuids).

## What building this surfaced (and why that's included here)

Three real logic bugs were found and fixed by actually running the parts of this codebase
that could run in a network-isolated, dependency-free sandbox, rather than only reading
the code back: a context-budget floor that silently ignored a caller's actual budget
request, a `KeyError` on a common early-return path in the tool-timing helper, and a
scheduler function that conflated "nothing left to schedule" with "the project succeeded."
Each is documented at its actual location
([06](06-context-engineering.md), [10](10-tool-system.md), [05](05-task-dag.md)) rather
than only summarized here, alongside the regression test that now covers it. This is
included deliberately: a project whose stated purpose is *verifiability* should be able to
show its own verification process, not just assert that the code is correct.
