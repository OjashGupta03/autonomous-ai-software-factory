from __future__ import annotations
import datetime as dt
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import Settings
from app.models.file import File
from app.models.test_run import TestRun, TestResult
from app.sandbox.docker_executor import DockerSandboxExecutor, SandboxExecutionRequest, SandboxUnavailableError, Workspace


async def run_integration_tests(db: AsyncSession, project_id: uuid.UUID, settings: Settings) -> TestRun:
    test_run = TestRun(project_id=project_id, trigger="integration", status="running", started_at=dt.datetime.utcnow())
    db.add(test_run)
    await db.commit()
    await db.refresh(test_run)

    result = await db.execute(select(File).where(File.project_id == project_id).order_by(File.path, File.version.desc()))
    all_files = result.scalars().all()
    latest_files = {}
    for f in all_files:
        if f.path not in latest_files:
            latest_files[f.path] = f.content

    workspace = Workspace(settings, str(project_id))
    try:
        workspace_dir = workspace.materialize(latest_files)
        try:
            executor = DockerSandboxExecutor(settings)
            request = SandboxExecutionRequest(
                command=["bash", "-c", "if [ -f backend/requirements.txt ]; then pip install -r backend/requirements.txt; elif [ -f requirements.txt ]; then pip install -r requirements.txt; fi && if [ -d backend ]; then cd backend && python3 -m pytest --no-header -v; else python3 -m pytest --no-header -v; fi"],
                workspace_dir=workspace_dir,
                timeout_seconds=settings.SANDBOX_TIMEOUT_SECONDS,
                network_disabled=False
            )
            exec_result = await executor.execute(request)
            test_run.status = "passed" if exec_result.success else "failed"
            message = exec_result.stdout + "\n" + exec_result.stderr
            result_status = "pass" if exec_result.success else ("error" if exec_result.timed_out else "fail")
            duration_ms = exec_result.execution_time_ms
        except SandboxUnavailableError as e:
            # FIX: previously an unavailable sandbox propagated as an
            # unhandled exception out of run_integration_tests, which
            # left the TestRun row stuck at status="running" forever and
            # crashed the whole run_project_job. A sandbox being
            # unavailable is itself real, reportable information ("tests
            # could not run"), not a crash.
            test_run.status = "failed"
            message = f"Sandbox unavailable: {e}"
            result_status = "error"
            duration_ms = 0.0

        test_run.finished_at = dt.datetime.utcnow()
        test_result = TestResult(test_run_id=test_run.id, test_name="pytest suite", status=result_status, duration_ms=duration_ms, message=message)
        db.add(test_result)
        await db.commit()
        await db.refresh(test_run)
    finally:
        workspace.cleanup()

    return test_run
