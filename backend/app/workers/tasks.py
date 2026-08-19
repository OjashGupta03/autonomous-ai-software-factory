"""
ARQ job functions (docs/17-worker-system.md).

Two jobs:
- `execute_task_job`: runs a single Task end-to-end (agent_execution_service).
  Enqueued once per ready task by ProjectRunner.dispatch_batch - this is
  where real concurrency comes from (ARQ runs up to `max_jobs` of these
  at once), not from LangGraph itself.
- `run_project_job`: drives a project's ProjectRunner.run_or_resume() to
  completion (or a human-approval pause) inside a worker process rather
  than inside the API request/response cycle, since a full project run
  can take much longer than an HTTP timeout should allow.

Each job opens its own DB session (workers are separate processes/tasks
from the API, so they cannot share the API's request-scoped session).
"""
from __future__ import annotations

import uuid

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionLocal

logger = get_logger(__name__)


async def execute_task_job(ctx: dict, task_id: str) -> None:
    from app.services.agent_execution_service import execute_task

    settings = get_settings()
    redis = ctx.get("redis")
    async with AsyncSessionLocal() as db:
        try:
            await execute_task(db, redis, settings, uuid.UUID(task_id))
        except Exception:
            logger.exception("execute_task_job failed", task_id=task_id)
            raise


async def run_project_job(ctx: dict, project_id: str) -> None:
    from app.orchestrator.runner import ProjectRunner

    settings = get_settings()
    redis = ctx.get("redis")
    async with AsyncSessionLocal() as db:
        async def enqueue(task_id: uuid.UUID) -> None:
            pool = ctx["arq_pool"]
            await pool.enqueue_job("execute_task_job", str(task_id))

        runner = ProjectRunner(uuid.UUID(project_id), db, redis, settings, enqueue_task=enqueue)
        try:
            await runner.run_or_resume()
        except Exception:
            logger.exception("run_project_job failed", project_id=project_id)
            raise


async def _startup(ctx: dict) -> None:
    configure_logging()
    from redis.asyncio import Redis

    settings = get_settings()
    ctx["redis"] = Redis.from_url(settings.REDIS_URL)
    # The worker enqueues its own follow-up jobs (execute_task_job, from
    # inside run_project_job) via a pool bound to the same Redis - stored
    # on ctx rather than re-created per job.
    from arq import create_pool

    ctx["arq_pool"] = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))


async def _shutdown(ctx: dict) -> None:
    redis = ctx.get("redis")
    if redis is not None:
        await redis.aclose()
    pool = ctx.get("arq_pool")
    if pool is not None:
        await pool.close()


class WorkerSettings:
    functions = [execute_task_job, run_project_job]
    on_startup = _startup
    on_shutdown = _shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().REDIS_URL)
    max_jobs = get_settings().MAX_PARALLEL_TASKS * 2  # headroom over the scheduler's own cap
    job_timeout = 3600  # 1 hour timeout for the orchestrator loop
