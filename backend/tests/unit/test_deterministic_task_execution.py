"""
Regression tests for the core bug in this report:
_execute_deterministic_task used to be an empty stub that marked every
scaffold/install/format task COMPLETED without doing anything.
"""
from __future__ import annotations
import uuid
import pytest
from sqlalchemy import select
from app.core.config import Settings
from app.core.constants import TaskStatus, TaskType
from app.models.file import File
from app.models.project import Project
from app.models.task import Task
from app.services.agent_execution_service import _execute_deterministic_task
from app.services import project_service
from app.schemas.project import ProjectCreate


@pytest.mark.asyncio
async def test_create_files_scaffold_actually_writes_the_files(db_session):
    owner = uuid.uuid4()
    from app.models.user import User
    from app.core.security import hash_password
    user = User(id=owner, email="scaffold@example.com", hashed_password=hash_password("x" * 8))
    db_session.add(user)
    await db_session.commit()

    project = await project_service.create_project(db_session, owner, ProjectCreate(name="P", requirement="x" * 20))

    task = Task(
        project_id=project.id, title="Scaffold backend", description="mkdir + main.py",
        task_type=TaskType.SCAFFOLD, assigned_agent_type=None,
        deterministic_payload={"action": "create_files", "files": {"backend/main.py": "", "backend/requirements.txt": "fastapi\n"}},
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    await _execute_deterministic_task(db_session, Settings(), task)
    await db_session.commit()

    assert task.status == TaskStatus.COMPLETED

    result = await db_session.execute(select(File).where(File.project_id == project.id))
    paths = sorted(f.path for f in result.scalars().all())
    assert paths == ["backend/main.py", "backend/requirements.txt"]

    # and attribution to the scaffold task itself (needed for the
    # files_modified fix to show anything for scaffold tasks too)
    result2 = await db_session.execute(select(File).where(File.created_by_task_id == task.id))
    assert len(result2.scalars().all()) == 2


@pytest.mark.asyncio
async def test_scaffold_task_with_no_payload_fails_loudly_instead_of_silently_completing(db_session):
    owner = uuid.uuid4()
    from app.models.user import User
    from app.core.security import hash_password
    user = User(id=owner, email="noop@example.com", hashed_password=hash_password("x" * 8))
    db_session.add(user)
    await db_session.commit()
    project = await project_service.create_project(db_session, owner, ProjectCreate(name="P2", requirement="x" * 20))

    task = Task(project_id=project.id, title="Scaffold with nothing to do", description="d",
                task_type=TaskType.SCAFFOLD, assigned_agent_type=None, deterministic_payload=None)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    with pytest.raises(RuntimeError, match="deterministic_payload"):
        await _execute_deterministic_task(db_session, Settings(), task)


@pytest.mark.asyncio
async def test_mkdir_run_command_is_treated_as_a_deliberate_noop(db_session):
    owner = uuid.uuid4()
    from app.models.user import User
    from app.core.security import hash_password
    user = User(id=owner, email="mkdir@example.com", hashed_password=hash_password("x" * 8))
    db_session.add(user)
    await db_session.commit()
    project = await project_service.create_project(db_session, owner, ProjectCreate(name="P3", requirement="x" * 20))

    task = Task(project_id=project.id, title="mkdir backend", description="d", task_type=TaskType.SCAFFOLD,
                assigned_agent_type=None, deterministic_payload={"action": "run_command", "argv": ["mkdir", "-p", "backend"]})
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    # Must NOT attempt to hit the (unavailable, in this sandbox) Docker
    # daemon for a bare mkdir - it should complete immediately.
    await _execute_deterministic_task(db_session, Settings(), task)
    assert task.status == TaskStatus.COMPLETED
