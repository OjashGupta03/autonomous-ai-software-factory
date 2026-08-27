"""
Regression test: create_tasks_from_plan must reject an unknown
dependency key instead of silently dropping the edge (the previous
behaviour), and decompose_tasks must reject a cyclic proposal before
writing anything - see runner.py::decompose_tasks.
"""
from __future__ import annotations
import uuid
import pytest
from app.services import task_service


@pytest.mark.asyncio
async def test_dependency_on_unknown_key_raises_instead_of_silently_dropping(db_session):
    owner = uuid.uuid4()
    from app.models.user import User
    from app.core.security import hash_password
    from app.services import project_service
    from app.schemas.project import ProjectCreate

    user = User(id=owner, email="dag@example.com", hashed_password=hash_password("x" * 8))
    db_session.add(user)
    await db_session.commit()
    project = await project_service.create_project(db_session, owner, ProjectCreate(name="P", requirement="x" * 20))

    with pytest.raises(ValueError, match="unknown task key"):
        await task_service.create_tasks_from_plan(db_session, project.id, plan_id=None, proposed_tasks=[
            {"key": "T1", "title": "t", "description": "d", "task_type": "schema_design", "agent_type": "coder", "depends_on": ["T-does-not-exist"]},
        ])


def test_scheduler_validate_dag_rejects_a_planner_style_cycle():
    from app.core.constants import TaskStatus
    from app.orchestrator.scheduler import CyclicDependencyError, TaskNode, validate_dag

    proposed = [
        {"key": "T1", "depends_on": ["T2"]},
        {"key": "T2", "depends_on": ["T1"]},
    ]
    nodes = [TaskNode(id=t["key"], status=TaskStatus.PENDING, depends_on=tuple(t["depends_on"])) for t in proposed]
    with pytest.raises(CyclicDependencyError):
        validate_dag(nodes)
