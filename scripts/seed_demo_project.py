#!/usr/bin/env python3
"""
Seeds one demo project (owner, requirement, a small realistic task DAG)
using the actual service layer - not raw SQL, not fixture JSON dumped
into the DB - so it exercises the same code path a real signup +
project-creation flow would. Useful for exploring the frontend/API
without waiting on a live LLM run.

This does NOT run the orchestrator (that needs a real model API key or
MODEL_PROVIDER_*=stub) - it only seeds a project structure so the UI has
something to show. See docs/20-local-development.md.

Usage (from backend/, with the venv/deps active and DATABASE_URL pointed
at a running Postgres):
    python ../scripts/seed_demo_project.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.project import ProjectCreate  # noqa: E402
from app.services import project_service, task_service  # noqa: E402

DEMO_EMAIL = "demo@factory.local"
DEMO_PASSWORD = "demo-password-123"

DEMO_REQUIREMENT = (
    "Build a URL shortening SaaS with authentication, PostgreSQL, analytics "
    "and a React dashboard."
)

DEMO_TASKS = [
    {"key": "T1", "title": "Design database schema", "description": "Design tables for users, links, and click analytics.",
     "task_type": "schema_design", "agent_type": "coder", "depends_on": [], "priority": 10},
    {"key": "T2", "title": "Scaffold backend project", "description": "Create the FastAPI project structure.",
     "task_type": "scaffold", "agent_type": None, "depends_on": [],
     "deterministic_payload": {"action": "create_files", "files": {"backend/README.md": "# Backend\n"}}},
    {"key": "T3", "title": "Implement link models", "description": "SQLAlchemy models for the schema from T1.",
     "task_type": "backend_implementation", "agent_type": "coder", "depends_on": ["T1", "T2"]},
    {"key": "T4", "title": "Implement auth endpoints", "description": "Register/login/JWT.",
     "task_type": "backend_implementation", "agent_type": "coder", "depends_on": ["T2"]},
    {"key": "T5", "title": "Implement shorten + redirect API", "description": "POST /links, GET /{code}.",
     "task_type": "backend_implementation", "agent_type": "coder", "depends_on": ["T3", "T4"]},
    {"key": "T6", "title": "Build dashboard UI", "description": "React dashboard listing the user's links and click counts.",
     "task_type": "frontend_implementation", "agent_type": "coder", "depends_on": ["T5"]},
    {"key": "T7", "title": "Integration tests", "description": "End-to-end coverage of create/redirect/analytics.",
     "task_type": "test_authoring", "agent_type": "tester", "depends_on": ["T6"]},
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        existing = await db.execute(select(User).where(User.email == DEMO_EMAIL))
        user = existing.scalar_one_or_none()
        if user is None:
            user = User(email=DEMO_EMAIL, hashed_password=hash_password(DEMO_PASSWORD), full_name="Demo User")
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"Created demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        else:
            print(f"Demo user already exists: {DEMO_EMAIL}")

        project = await project_service.create_project(
            db, user.id,
            ProjectCreate(name="URL Shortener SaaS (demo)", requirement=DEMO_REQUIREMENT, token_budget=200_000),
        )
        print(f"Created project: {project.id} - {project.name}")

        tasks = await task_service.create_tasks_from_plan(db, project.id, plan_id=None, proposed_tasks=DEMO_TASKS)
        print(f"Seeded {len(tasks)} tasks.")
        print("\nLog in via POST /api/v1/auth/login and open this project in the frontend to explore the UI.")
        print("To actually run it, POST /api/v1/projects/{id}/start (needs a real model API key, or")
        print("MODEL_PROVIDER_*=stub in .env for a $0 dry run).")


if __name__ == "__main__":
    asyncio.run(main())
