# Autonomous AI Software Factory

An agentic platform that takes a natural-language software requirement and autonomously
plans, decomposes, implements, tests, debugs, and integrates it - while treating "how
much intelligence does this step actually need" as the central design question, not an
afterthought.

## Problem

Multi-agent LLM coding systems tend to waste tokens: every step calls an expensive model,
agents replay entire conversation histories to each other, and "more agents talking" gets
mistaken for "more capable system."

## Solution

A stateful orchestrator (LangGraph) sits on top of a deterministic core: a task DAG
scheduler, a model router, and a context manager that all make "should we spend an LLM
call here, and on what" decisions using plain Python, not another model call. Six
specialized agents (Planner, Coder, Reviewer, Debugger, Tester, Documenter) do the actual
reasoning work, each scoped to a minimal, task-specific context and a narrow tool set.
Every execution is tracked - tokens, cost, retries, cache hits - against Postgres, and
compared to a documented estimate of what a naive pipeline would have cost.

## The core principle

> Use intelligence only where intelligence is required.

A task that's mechanical (scaffold a folder, install dependencies, format code) never
touches an LLM - it's routed to a deterministic tool call instead. A task that needs
reasoning is routed to a model tier sized for its difficulty. The Planner is the one
deliberate exception (see [docs/23-design-decisions.md](docs/23-design-decisions.md)) -
everywhere else, using *fewer* LLM calls than a naive multi-agent system is the goal, not
a compromise.

## What makes this genuinely agentic, not a scripted pipeline

- **Autonomous decision-making**: scheduling, model routing, and failure recovery are all
  made by inspecting real, persisted state - not by following a fixed script. See
  [docs/04-orchestrator.md](docs/04-orchestrator.md).
- **Real state, not conversation replay**: Postgres is the source of truth; the LangGraph
  runtime state carries only routing-relevant bookkeeping. See
  [docs/06-context-engineering.md](docs/06-context-engineering.md).
- **Real dependencies**: tasks form a DAG with genuine parallel execution where the graph
  allows it. See [docs/05-task-dag.md](docs/05-task-dag.md).
- **Real tool use**: agents act through tools with structured results - nothing is
  narrated into existence. See [docs/10-tool-system.md](docs/10-tool-system.md).
- **Real feedback loops**: test failures route back into the same scheduling loop that
  drives the initial build, not a separate bolted-on retry script. See
  [docs/03-agentic-workflow.md](docs/03-agentic-workflow.md).
- **Real verification**: tests run in an isolated sandbox and their actual pass/fail
  status - not an LLM's opinion of it - drives what happens next. See
  [docs/11-code-execution-sandbox.md](docs/11-code-execution-sandbox.md).
- **Real recovery**: failures are classified deterministically and either retried,
  escalated to a Debug agent with the specific error, or handed to a human - never
  retried blindly forever. See [docs/12-failure-recovery.md](docs/12-failure-recovery.md).
- **Cost-aware by construction**: every one of the above is also a token-optimization
  decision. See [docs/07-token-optimization.md](docs/07-token-optimization.md).

## Quick start

```bash
cp .env.example .env
# edit .env - add an OpenAI/Anthropic key, or leave MODEL_PROVIDER_*=stub for a $0 dry run

docker build -f docker/sandbox.Dockerfile -t factory-sandbox:latest .
docker compose up --build
```

Backend: `http://localhost:8000/docs` · Frontend: `http://localhost:5173`

Full setup (including running without Docker): [docs/20-local-development.md](docs/20-local-development.md).

## Example

```
POST /projects
{
  "name": "URL Shortener SaaS",
  "requirement": "Build a URL shortening SaaS with authentication, PostgreSQL, analytics and a React dashboard."
}
```

Then `POST /projects/{id}/start` and watch it happen live at
`GET /projects/{id}/events`, or in the frontend's project workspace.

## Repository layout

```
backend/    FastAPI app: orchestrator, agents, tools, sandbox, API, workers, tests
frontend/   React + TypeScript + Vite, dark "control room" design system
docker/     The sandbox execution image (built separately from docker-compose)
docs/       24 documents - what the system does AND why it's built this way
scripts/    Demo-project seeding, dev helpers
```

## Documentation

Start at [docs/01-overview.md](docs/01-overview.md). Every major decision has a "why"
explained in [docs/23-design-decisions.md](docs/23-design-decisions.md). Full index:

| | | |
|---|---|---|
| [01 Overview](docs/01-overview.md) | [09 Agent design](docs/09-agent-design.md) | [17 Worker system](docs/17-worker-system.md) |
| [02 Architecture](docs/02-architecture.md) | [10 Tool system](docs/10-tool-system.md) | [18 Observability](docs/18-observability.md) |
| [03 Agentic workflow](docs/03-agentic-workflow.md) | [11 Sandbox](docs/11-code-execution-sandbox.md) | [19 Security](docs/19-security.md) |
| [04 Orchestrator](docs/04-orchestrator.md) | [12 Failure recovery](docs/12-failure-recovery.md) | [20 Local development](docs/20-local-development.md) |
| [05 Task DAG](docs/05-task-dag.md) | [13 Human in the loop](docs/13-human-in-the-loop.md) | [21 Testing](docs/21-testing.md) |
| [06 Context engineering](docs/06-context-engineering.md) | [14 Database design](docs/14-database-design.md) | [22 Deployment](docs/22-deployment.md) |
| [07 Token optimization](docs/07-token-optimization.md) | [15 API](docs/15-api.md) | [23 Design decisions](docs/23-design-decisions.md) |
| [08 Model routing](docs/08-model-routing.md) | [16 Frontend](docs/16-frontend.md) | [24 Troubleshooting](docs/24-troubleshooting.md) |

## Known limitations

This repository was built in a sandboxed environment with **no network access, no Docker
daemon, and no installable Python/Node packages**. Every piece of pure-Python logic that
could be exercised without a third-party dependency *was* actually run - not just
read back - and three real bugs were found and fixed in the process (see
[docs/21-testing.md](docs/21-testing.md) for the full account). What could not be verified
there: `pytest` against the real FastAPI/SQLAlchemy/LangGraph stack, `npm run build`
(TypeScript compilation), and anything touching a real LLM provider, Postgres, or the
Docker sandbox executor. [docs/20-local-development.md](docs/20-local-development.md)
lists the exact first-run checks to close that gap, in order of value.

## License

MIT - see [LICENSE](LICENSE).
