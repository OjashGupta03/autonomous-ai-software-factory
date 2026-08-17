"""
Async SQLAlchemy engine/session factory.

A single engine is created per process from settings.DATABASE_URL. Tests
override `get_db` (see backend/tests/conftest.py) to point at an in-memory
SQLite database via aiosqlite, so the bulk of the service layer can be
exercised without a real Postgres instance.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_pre_ping=True,
    pool_size=settings.DATABASE_POOL_SIZE if "sqlite" not in settings.DATABASE_URL else None,
) if "sqlite" not in settings.DATABASE_URL else create_async_engine(
    settings.DATABASE_URL, echo=settings.DATABASE_ECHO
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, autoflush=False, class_=AsyncSession
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
