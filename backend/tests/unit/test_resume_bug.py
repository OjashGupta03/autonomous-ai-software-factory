"""
Regression test for Bug #4 ("The Resume Bug"): resuming a project that
has an active ProjectPlan but zero Task rows must re-run decomposition,
not jump straight to scheduling with nothing to schedule.
"""
from __future__ import annotations
import uuid
import pytest
from app.services import task_service


@pytest.mark.asyncio
async def test_project_has_tasks_is_false_before_decomposition_and_true_after(db_session):
    owner = uuid.uuid4()
    from app.models.user import User
    from app.core.security import hash_password
    from app.services import project_service
    from app.schemas.project import ProjectCreate

    user = User(id=owner, email="resume@example.com", hashed_password=hash_password("x" * 8))
    db_session.add(user)
    await db_session.commit()
    project = await project_service.create_project(db_session, owner, ProjectCreate(name="P", requirement="x" * 20))

    assert await task_service.project_has_tasks(db_session, project.id) is False

    await task_service.create_tasks_from_plan(db_session, project.id, plan_id=None, proposed_tasks=[
        {"key": "T1", "title": "t", "description": "d", "task_type": "schema_design", "agent_type": "coder", "depends_on": []},
    ])

    assert await task_service.project_has_tasks(db_session, project.id) is True
