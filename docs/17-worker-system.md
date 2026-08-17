# 17 - Worker System

## The decision: ARQ, not Celery, not Kafka, not Dramatiq

**Why a worker system at all**: a single task execution can involve a multi-turn agent
tool-calling loop plus a sandboxed test run - well past what an HTTP request/response
cycle should hold open. `POST /projects/{id}/start` returns `202` immediately and the real
work happens in a worker process.

**Why ARQ over Celery**: this codebase is async top to bottom (FastAPI, SQLAlchemy 2.0
async, async LangChain calls). Celery's execution model is fundamentally synchronous-
worker-per-process; running it alongside an async codebase means either wrapping every
call in `asyncio.run()` inside sync tasks (works, but fights the framework) or adopting
Celery's own newer async support, which is less mature and more complex than the
problem here calls for. ARQ is async-native (job functions are `async def`), Redis-backed
(one less system to run - see below), and its entire configuration surface is a handful of
settings (`app/workers/tasks.py::WorkerSettings`) rather than Celery's much larger
configuration space. For this project's actual concurrency needs (bounded by
`MAX_PARALLEL_TASKS`, not "thousands of jobs/sec"), ARQ's simplicity is a better fit than
Celery's generality.

**Why not Kafka**: Kafka earns its complexity when you need a durable, replayable log
consumed by multiple independent consumer groups at high throughput. Nothing here needs
that - job dispatch is "run this task once", not "publish an event many services react to
independently". Introducing Kafka would mean running and operating a third stateful
system for a problem Redis's list-based queue already solves at this scale. The project
brief explicitly warns against this exact anti-pattern ("Kafka should ONLY be introduced
if there is a real architectural reason for it") and no such reason exists here.

## What Redis is actually doing (three jobs, one instance)

1. **ARQ's job queue** - `execute_task_job` (one task) and `run_project_job` (one
   project's orchestrator run).
2. **Pub/sub fan-out for live events** - `app/services/event_service.py` publishes every
   durably-written `ProjectEvent` to a per-project channel; `app/events/sse.py` subscribes
   on behalf of connected frontend clients. See [16-frontend.md](16-frontend.md).
3. **An LLM-response cache key space** (`llm_clients._cache_key`) - the hashing is
   implemented; wiring a cache-check into the agent loop before an LLM call is a natural
   next step (see [24-troubleshooting.md](24-troubleshooting.md) / future improvements in
   the top-level summary) but is not active by default in this repository.

Running these three responsibilities on one Redis instance, rather than three separate
systems, is a direct application of the project's own stated preference for the simplest
architecture that's technically justified.

## The two jobs

- **`execute_task_job(task_id)`** - runs `agent_execution_service.execute_task`. This is
  where real concurrency comes from: `dispatch_batch` enqueues every ready task
  independently, and ARQ's worker pool (`max_jobs`, sized from `MAX_PARALLEL_TASKS`) runs
  up to that many concurrently.
- **`run_project_job(project_id)`** - drives `ProjectRunner.run_or_resume()`. Enqueued on
  project start, and again by the approvals endpoint after a human decision.

Each job opens its own DB session (`AsyncSessionLocal`) since workers are separate
processes from the API and cannot share a request-scoped session.

## Why LangGraph doesn't do this fan-out itself

LangGraph *can* express parallel branches, but this project's actual concurrency need -
"run N independent, potentially long-running, sandboxed task executions, with retries and
timeouts, across possibly multiple worker processes" - is a distributed job scheduling
problem, not a graph-branching problem. Fighting LangGraph's single-process execution
model to get that would add complexity without benefit. Instead: LangGraph owns the
project-level *phase* state machine (plan -> schedule -> await -> evaluate -> ...), and
ARQ owns concurrent *task* execution underneath one `await_batch` node. See
[04-orchestrator.md](04-orchestrator.md).
