# 22 - Deployment

This repository ships a solid local/single-host Docker Compose setup
([20-local-development.md](20-local-development.md)); it does not ship a production
Kubernetes/Terraform/CI configuration, since a real deployment target's specifics
(cloud provider, secrets manager, ingress, autoscaling policy) would make one opinionated
choice here likely wrong for whoever actually deploys this. What follows is the shape a
production deployment should take, and the parts of this codebase already built for it.

## Container images

`backend/Dockerfile` and `frontend/Dockerfile` are already multi-purpose: the backend
image runs as either the API (`uvicorn ...`) or the worker (`arq
app.workers.tasks.WorkerSettings`) depending on the command, so a production deployment
needs exactly two application images (plus the sandbox image, built and pushed
separately - it is never deployed as a running service, only as an image the backend/
worker containers `docker run` against; those containers need Docker-socket or
Docker-in-Docker access wherever they run).

## Configuration

Every tunable is an environment variable (`app/core/config.py::Settings`) - nothing about
scaling this system requires a code change. The variables most worth reviewing per
environment: `MAX_PARALLEL_TASKS` and ARQ's `max_jobs` (worker concurrency),
`SANDBOX_MEMORY_LIMIT`/`SANDBOX_CPU_LIMIT` (sized to actual host capacity),
`DEFAULT_PROJECT_TOKEN_BUDGET` and `HIGH_COST_ESCALATION_USD` (cost controls), and of
course the model/provider variables.

## Database

`alembic upgrade head` against a real, persistent Postgres instance (not the
`docker-compose.yml` service, which uses an unauthenticated local volume suited to
development). The initial migration generates schema from `Base.metadata` (see
[14-database-design.md](14-database-design.md)) - review the generated DDL once against
your target Postgres version before a first production run.

## Workers

Horizontal scaling is exactly "run more `arq app.workers.tasks.WorkerSettings` processes
pointed at the same Redis" - ARQ's queue semantics make this safe without additional
coordination. See [17-worker-system.md](17-worker-system.md).

## What's explicitly not here

- No CI pipeline (no `.github/workflows/`). The most valuable one to add first would run
  exactly the checks [21-testing.md](21-testing.md) describes as "written but not
  executed" - `pytest`, `npm run build`, `npm run test` - against real dependencies.
- No secrets-manager integration (`.env` only).
- No autoscaling policy, no ingress/TLS termination configuration, no log aggregation
  target beyond stdout (structlog - see [18-observability.md](18-observability.md)).
- No multi-tenancy beyond per-user project ownership - see
  [19-security.md](19-security.md) for what that does and doesn't cover.

Treat this repository as the application layer, not the infrastructure layer.
