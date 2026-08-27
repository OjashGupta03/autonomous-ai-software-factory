from __future__ import annotations
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.constants import ApprovalType
from app.services import approval_service, project_service, task_service
from app.schemas.project import ProjectCreate


async def _seed_project_with_tasks(db: AsyncSession, owner_id) -> tuple:
    if isinstance(owner_id, str):
        owner_id = uuid.UUID(owner_id)
    project = await project_service.create_project(db, owner_id, ProjectCreate(name="Seeded Project", requirement="A requirement long enough to pass validation."))
    tasks = await task_service.create_tasks_from_plan(db, project.id, plan_id=None, proposed_tasks=[
        {"key": "T1", "title": "Design schema", "description": "Design the DB schema.", "task_type": "schema_design", "agent_type": "coder", "depends_on": []},
        {"key": "T2", "title": "Implement models", "description": "Implement SQLAlchemy models.", "task_type": "backend_implementation", "agent_type": "coder", "depends_on": ["T1"]},
    ])
    return project, tasks


@pytest.mark.asyncio
async def test_task_graph_endpoint_reflects_seeded_dependencies(client: AsyncClient, db_session: AsyncSession, test_user_and_token: dict):
    project, tasks = await _seed_project_with_tasks(db_session, test_user_and_token["user"]["id"])
    response = await client.get(f"/api/v1/projects/{project.id}/tasks/graph", headers=test_user_and_token["headers"])
    assert response.status_code == 200
    nodes = response.json()["nodes"]
    assert len(nodes) == 2
    by_title = {n["title"]: n for n in nodes}
    assert by_title["Design schema"]["depends_on"] == []
    assert len(by_title["Implement models"]["depends_on"]) == 1


@pytest.mark.asyncio
async def test_approval_list_and_decide_flow(client: AsyncClient, db_session: AsyncSession, test_user_and_token: dict):
    project, tasks = await _seed_project_with_tasks(db_session, test_user_and_token["user"]["id"])
    approval = await approval_service.create_approval(db_session, project.id, ApprovalType.REPEATED_FAILURE, "Task failed 3 times.", task_id=tasks[0].id)
    pending = await client.get(f"/api/v1/projects/{project.id}/approvals", headers=test_user_and_token["headers"])
    assert pending.status_code == 200
    assert len(pending.json()) == 1
    decide = await client.post(f"/api/v1/projects/{project.id}/approvals/{approval.id}/decide", json={"decision": "approved", "note": "Looks fine, retry it."}, headers=test_user_and_token["headers"])
    assert decide.status_code == 200
    assert decide.json()["status"] == "approved"
    pending_after = await client.get(f"/api/v1/projects/{project.id}/approvals", headers=test_user_and_token["headers"])
    assert len(pending_after.json()) == 0


@pytest.mark.asyncio
async def test_modified_approval_decision_is_actually_applied_to_the_retried_task(client: AsyncClient, db_session: AsyncSession, test_user_and_token: dict):
    """FIX regression test: previously ApprovalDecision.modified_instruction
    was accepted by the API and silently discarded. This confirms it now
    actually lands on the task the human was correcting."""
    project, tasks = await _seed_project_with_tasks(db_session, test_user_and_token["user"]["id"])
    task = tasks[0]
    approval = await approval_service.create_approval(db_session, project.id, ApprovalType.REPEATED_FAILURE, "Task failed 3 times.", task_id=task.id)

    decide = await client.post(
        f"/api/v1/projects/{project.id}/approvals/{approval.id}/decide",
        json={"decision": "modified", "modified_instruction": "Use SQLite instead of Postgres for this environment."},
        headers=test_user_and_token["headers"],
    )
    assert decide.status_code == 200

    refreshed = await task_service.get_task(db_session, task.id)
    assert refreshed.human_instruction_override == "Use SQLite instead of Postgres for this environment."
    assert refreshed.status.value == "pending"
    assert refreshed.attempt_count == 1
