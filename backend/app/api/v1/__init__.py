"""Aggregates every v1 router into one APIRouter that main.py mounts once."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import agents, approvals, auth, events, files, metrics, projects, tasks, test_runs

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(agents.router)
api_router.include_router(files.router)
api_router.include_router(test_runs.router)
api_router.include_router(approvals.router)
api_router.include_router(metrics.router)
api_router.include_router(events.router)
