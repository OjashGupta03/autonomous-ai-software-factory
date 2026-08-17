"""
Automated testing (docs/21-testing.md at the app level; this module is
what app/orchestrator/graph.py's `run_integration_tests` node calls into).

Running the suite is a deterministic tool call (TestRunnerTool, which
executes pytest/npm test inside the sandbox) - no LLM involved. Parsing
raw pytest/jest output into structured pass/fail rows uses a small
regex-based parser here rather than an LLM, for the same reason the
scheduler is deterministic: "did the tests pass" is a parsing problem,
not a reasoning problem.
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.test_run import TestResult, TestRun
from app.tools.exec_tools import TestRunnerTool

_PYTEST_SUMMARY_RE = re.compile(
    r"(?P<passed>\d+) passed|(?P<failed>\d+) failed|(?P<errors>\d+) error"
)


def _parse_pytest_summary(stdout: str) -> tuple[int, int, int]:
    passed = failed = errors = 0
    for m in _PYTEST_SUMMARY_RE.finditer(stdout):
        if m.group("passed"):
            passed = int(m.group("passed"))
        elif m.group("failed"):
            failed = int(m.group("failed"))
        elif m.group("errors"):
            errors = int(m.group("errors"))
    return passed, failed, errors


async def run_integration_tests(
    db: AsyncSession, project_id: uuid.UUID, settings: Settings, task_id: uuid.UUID | None = None
) -> TestRun:
    test_run = TestRun(project_id=project_id, task_id=task_id, trigger="integration", status="running")
    db.add(test_run)
    await db.commit()
    await db.refresh(test_run)

    tool = TestRunnerTool(db, project_id, settings)
    result = await tool.run()
    stdout = (result.output or {}).get("stdout", "") if isinstance(result.output, dict) else ""
    passed, failed, errors = _parse_pytest_summary(stdout)

    test_run.status = "passed" if result.success and failed == 0 and errors == 0 else "failed"
    if failed or errors:
        db.add(TestResult(test_run_id=test_run.id, test_name="suite summary", status="fail",
                           duration_ms=result.execution_time_ms, message=stdout[-2000:]))
    elif passed:
        db.add(TestResult(test_run_id=test_run.id, test_name="suite summary", status="pass",
                           duration_ms=result.execution_time_ms, message=f"{passed} passed"))
    else:
        # Suite ran but produced no recognizable summary line (e.g. an
        # empty test suite, or a crash before pytest could report one) -
        # record it as a failure so the orchestrator does not silently
        # treat "nothing happened" as success.
        db.add(TestResult(test_run_id=test_run.id, test_name="suite summary", status="error",
                           duration_ms=result.execution_time_ms, message=(result.error or stdout)[-2000:]))
        test_run.status = "failed"

    await db.commit()
    await db.refresh(test_run)
    return test_run
