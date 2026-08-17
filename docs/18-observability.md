# 18 - Observability

## Structured logging

`app/core/logging.py` configures `structlog` with a consistent processor chain
(contextvars merge, log level, logger name, ISO timestamps) and two renderers: a
human-readable console renderer for local development, JSON for `LOG_JSON=true` in
production. Every HTTP request gets a `request_id` (generated in `main.py`'s middleware,
also returned as an `X-Request-ID` response header) so a frontend error report can be
correlated with backend logs.

## What gets tracked, and where

The project brief's list (`project_id`, `task_id`, `agent_id`, `run_id`, event type,
duration, tokens, model, status) is not a logging convention layered on top of the data
model here - it *is* the data model. Every field in that list corresponds to an actual
column on `AgentRun`, `TokenUsage`, `ToolCall`, or `ProjectEvent` (see
[14-database-design.md](14-database-design.md)), queried by the metrics API
([15-api.md](15-api.md)) rather than grepped out of log files. Logs are for debugging a
specific process; the database is the system of record for anything the product surfaces.

## The event log doubles as an audit trail

`project_events` is append-only and durable - every event the frontend can render live
(planner started, task ready, tool called, file modified, tests finished, approval
requested, ...) is written there *before* being published to Redis for live fan-out (see
[17-worker-system.md](17-worker-system.md)), so a client that connects after a run has
already started can replay the last 100 events rather than seeing a blank feed, and the
full history survives independent of whether anyone was watching live.

## OpenTelemetry

Not wired in this repository. The structured-logging + durable-event-log combination
covers this project's actual debugging and product needs without adding an OTel
collector to the deployment surface. `app/observability/` exists as the place a tracing
integration would go if a deployment needed distributed traces across the API, workers,
and sandbox containers - noted here as a real gap, not silently omitted.
