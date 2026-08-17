"""
Shared pytest fixtures.

`db_session` and `client` swap the app's Postgres engine for an
in-memory aiosqlite database via FastAPI's dependency_overrides, so the
integration tests in tests/integration/ exercise real service-layer logic
(actual SQL, actual ORM relationships) without requiring a running
Postgres instance - only `pip install -r backend/requirements-dev.txt`.
A handful of Postgres-specific column types (native UUID, JSON) are
supported by SQLite through SQLAlchemy's generic types where used, but
this is still not a substitute for testing against real Postgres before
a production deploy - see docs/21-testing.md for what this suite does
and does not cover.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db


@pytest_asyncio.fixture
async def db_engine():
    # StaticPool + a shared in-memory DSN keeps ALL connections (across
    # the test and the app's request handlers) pointed at the SAME
    # in-memory database for the life of the test - a plain
    # ":memory:" DSN would give every new connection its own empty DB.
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        import app.models  # noqa: F401 - registers all models on Base.metadata
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    from app.main import app

    async def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user_and_token(client: AsyncClient) -> dict:
    email = f"{uuid.uuid4()}@example.com"
    password = "correct-horse-battery-staple"
    register = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert register.status_code == 201, register.text
    login = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"user": register.json(), "token": token, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def settings():
    return get_settings()
