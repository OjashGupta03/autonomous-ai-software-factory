# 02 - Architecture

## System diagram

```mermaid
flowchart TB
    subgraph Client
        FE["React + TypeScript frontend<br/>(Vite, TanStack Query, SSE)"]
    end

    subgraph API["Backend - FastAPI"]
        REST["REST API (/api/v1/*)"]
        SSE["SSE stream (/projects/{id}/events)"]
    end

    subgraph Orch["Orchestration"]
        Graph["LangGraph workflow<br/>(graph.py)"]
        Scheduler["Deterministic scheduler<br/>(scheduler.py)"]
        Router["Model router<br/>(model_router.py)"]
        CtxMgr["Context manager<br/>(context_manager.py)"]
    end

    subgraph Agents
        Planner
        Coder
        Reviewer
        Debugger
        Tester
        Documenter
    end

    subgraph Workers["ARQ Worker Pool"]
        W1["execute_task_job"]
        W2["run_project_job"]
    end

    subgraph Sandbox["Docker Sandbox"]
        SB["Isolated, resource-limited,<br/>network-disabled containers"]
    end

    FE -->|REST| REST
    FE <-->|live events| SSE
    REST --> Orch
    W2 --> Graph
    Graph --> Scheduler
    Graph -->|enqueue ready tasks| W1
    W1 --> Router
    Router -->|deterministic| Sandbox
    Router -->|needs reasoning| CtxMgr
    CtxMgr --> Agents
    Agents -->|tool calls| Sandbox
    Agents -->|tool calls| DB[(PostgreSQL)]
    W1 --> DB
    W1 -->|publish| Redis[(Redis)]
    Redis -->|pub/sub| SSE
    Workers -.->|queue| Redis
    REST --> DB
```

## Component responsibilities

**FastAPI backend** (`backend/app/api`) - thin REST layer: auth, CRUD for
projects/tasks/files/approvals, metrics queries, and the SSE stream. Contains no
orchestration logic itself; every non-trivial handler delegates to `app/services`.

**Orchestrator** (`backend/app/orchestrator`) - the decision-making core. See
[04-orchestrator.md](04-orchestrator.md) for the full breakdown of what lives where and why.

**Agents** (`backend/app/agents`) - six thin configurations (system prompt + tool set +
model tier) of one shared ReAct-style tool-calling loop (`agents/base.py`). See
[09-agent-design.md](09-agent-design.md).

**Tools** (`backend/app/tools`) - the only way an agent affects the world. Split into
DB-backed tools (file read/write/search - safe, no execution) and sandbox-backed tools
(test/lint/format/shell - always run inside Docker). See [10-tool-system.md](10-tool-system.md).

**Worker pool** (`backend/app/workers`, ARQ) - runs `execute_task_job` (one task,
end-to-end) and `run_project_job` (drives a `ProjectRunner` through the graph) outside the
request/response cycle. See [17-worker-system.md](17-worker-system.md).

**Sandbox** (`backend/app/sandbox`, `docker/sandbox.Dockerfile`) - isolated execution for
anything that runs generated code. See [11-code-execution-sandbox.md](11-code-execution-sandbox.md).

**Frontend** (`frontend/`) - React + TypeScript + Vite. See [16-frontend.md](16-frontend.md).

## Data flow for one task

```mermaid
sequenceDiagram
    participant Sched as schedule_batch
    participant ARQ as ARQ worker
    participant Router as model_router
    participant Ctx as context_manager
    participant Agent as ToolCallingAgent
    participant Tool as file_writer / test_runner
    participant DB as PostgreSQL

    Sched->>ARQ: enqueue execute_task_job(task_id)
    ARQ->>Router: route_task(task_type, attempt_count)
    alt deterministic task_type
        Router-->>ARQ: DETERMINISTIC (no LLM)
        ARQ->>Tool: run directly
    else needs reasoning
        Router-->>ARQ: tier + reason
        ARQ->>Ctx: build_task_context(task, deps, files)
        Ctx-->>Agent: minimal prompt
        loop tool-calling loop (bounded)
            Agent->>Tool: file_reader / file_writer / ...
            Tool-->>Agent: ToolResult
        end
        Agent-->>ARQ: final summary + usage
    end
    ARQ->>DB: record AgentRun, ToolCalls, TokenUsage, Task status
    ARQ->>DB: publish_event(TASK_SUCCEEDED / TASK_FAILED)
```

## Why this shape

The two things that make this "genuinely agentic" rather than a scripted pipeline are (1)
the graph's conditional routing genuinely branches on runtime state - a project with no
failures never visits `handle_failures`; a project with a clean build never revisits it
after tests pass once - and (2) tasks are dispatched as a real concurrent batch to a real
worker pool, not simulated with `asyncio.sleep`. See [23-design-decisions.md](23-design-decisions.md)
for the alternatives that were considered and rejected.
