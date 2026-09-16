# 20 - Local Development

## Prerequisites

- Docker + Docker Compose
- An API key for at least one of OpenAI or Anthropic (or run in `stub` dry-run mode - see
  [08-model-routing.md](08-model-routing.md) - to exercise the orchestration without one)

## Fastest path: Docker Compose

```bash
cp .env.example .env
# edit .env: set OPENAI_API_KEY and/or ANTHROPIC_API_KEY, or leave the
# MODEL_PROVIDER_* vars as "stub" for a zero-cost dry run

docker build -f docker/sandbox.Dockerfile -t daedalus-sandbox:latest .

docker compose up --build
```

This starts Postgres, Redis, the backend (auto-runs `alembic upgrade head` before
`uvicorn`), a worker, and the frontend. Backend: `http://localhost:8000` (`/docs` for
interactive API docs). Frontend: `http://localhost:5173`.

The sandbox image is built manually and separately (not part of `docker compose up`)
because it is not a long-running service - see
[11-code-execution-sandbox.md](11-code-execution-sandbox.md).

## Running the backend without Docker

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Point DATABASE_URL at a local Postgres, or use SQLite for a quick spin:
export DATABASE_URL="sqlite+aiosqlite:///./dev.db"
export REDIS_URL="redis://localhost:6379/0"   # a local Redis is still needed for workers/events

alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal, start a worker:

```bash
arq app.workers.tasks.WorkerSettings
```

## Running the frontend without Docker

```bash
cd frontend
npm install
npm run dev
```

Vite's dev server proxies `/api` to `http://localhost:8000` (`vite.config.ts`) - no CORS
configuration needed for local development.

## First things to verify in your own environment

This repository was built in a sandbox with no network access, no Docker daemon, and no
installable Python/Node packages - see [21-testing.md](21-testing.md) for exactly what
that did and didn't allow validating before it reached you. On first run, in order:

1. `pip install -r backend/requirements-dev.txt && pytest backend/tests -q` - confirms
   every package version resolves and the full test suite (unit + integration) actually
   passes against real FastAPI/SQLAlchemy/LangGraph, not just the subset this repo's
   authoring environment could execute directly.
2. `cd frontend && npm install && npm run build` - confirms the TypeScript actually
   compiles. Every `.tsx`/`.ts` file was checked for brace balance and that every import
   resolves to a real export, but that is not a substitute for `tsc`.
3. `docker compose up --build` - confirms the Dockerfiles and compose wiring work
   end-to-end, including Alembic running against real Postgres and the worker connecting
   to real Redis.
4. Build the sandbox image and run one project end-to-end with a real API key - confirms
   `DockerSandboxExecutor` behaves as documented against a real Docker daemon (untested in
   the authoring environment - see [11-code-execution-sandbox.md](11-code-execution-sandbox.md)).

If any of these surface an issue, [24-troubleshooting.md](24-troubleshooting.md) is the
place to check first, and it's also the most useful place to add to.

## Seeding a demo project

`scripts/seed_demo_project.py` inserts a project + requirement via the real service layer
(not fabricated data) using the project brief's own example ("Build a URL shortening SaaS
with authentication, PostgreSQL, analytics and a React dashboard"). It does not fake an
agent run - starting the actual build still requires a real (or `stub`) model provider.
