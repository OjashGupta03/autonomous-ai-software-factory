from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.file import File
from app.models.test_run import TestRun, TestResult
from app.sandbox.docker_executor import DockerSandboxExecutor, SandboxExecutionRequest, Workspace


async def run_integration_tests(db: AsyncSession, project_id: uuid.UUID, settings: Settings) -> TestRun:
    test_run = TestRun(
        project_id=project_id,
        trigger="integration",
        status="running",
        started_at=dt.datetime.utcnow(),
    )
    db.add(test_run)
    await db.commit()
    await db.refresh(test_run)

    # 1. Fetch all latest files for the project
    result = await db.execute(
        select(File)
        .where(File.project_id == project_id)
        .order_by(File.path, File.version.desc())
    )
    all_files = result.scalars().all()

    # Deduplicate to get only the latest version of each file path
    latest_files = {}
    for f in all_files:
        if f.path not in latest_files:
            latest_files[f.path] = f.content

    # 2. Materialize workspace
    workspace = Workspace(settings, str(project_id))
    try:
        workspace_dir = workspace.materialize(latest_files)
        
        # 3. Execute tests
        executor = DockerSandboxExecutor(settings)
        request = SandboxExecutionRequest(
            command=["pytest", "--no-header", "-v"],
            workspace_dir=workspace_dir,
            timeout_seconds=settings.SANDBOX_TIMEOUT_SECONDS,
        )
        exec_result = await executor.execute(request)
        
        # 4. Record results
        test_run.status = "passed" if exec_result.success else "failed"
        test_run.finished_at = dt.datetime.utcnow()
        
        test_result = TestResult(
            test_run_id=test_run.id,
            test_name="pytest suite",
            status="pass" if exec_result.success else ("error" if exec_result.timed_out else "fail"),
            duration_ms=exec_result.execution_time_ms,
            message=exec_result.stdout + "\n" + exec_result.stderr,
        )
        db.add(test_result)
        await db.commit()
        await db.refresh(test_run)
        
    finally:
        workspace.cleanup()
        
    return test_run
