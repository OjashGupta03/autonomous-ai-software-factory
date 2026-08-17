"""FastAPI dependency providers - DB session, current user, Redis, ARQ pool."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


@lru_cache
def _redis_singleton(redis_url: str) -> Redis:
    return Redis.from_url(redis_url)


async def get_redis(settings: Settings = Depends(get_settings)) -> Redis:
    return _redis_singleton(settings.REDIS_URL)


async def get_arq_pool(settings: Settings = Depends(get_settings)):
    from arq import create_pool
    from arq.connections import RedisSettings

    # Cheap to create per-request for this project's scale; if this ever
    # becomes a hot path, promote to an app.state-held singleton created
    # once in main.py's lifespan instead.
    return await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_error
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except jwt.PyJWTError as e:
        raise credentials_error from e

    from sqlalchemy import select

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_error
    return user
