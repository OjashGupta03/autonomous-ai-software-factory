"""Auth flow: register -> login -> access a protected route."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_then_login_then_me(client: AsyncClient):
    email = "auth-flow@example.com"
    password = "correct-horse-battery-staple"

    register = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert register.status_code == 201, register.text
    assert register.json()["email"] == email

    login = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


@pytest.mark.asyncio
async def test_duplicate_registration_is_rejected(client: AsyncClient):
    email = "dupe@example.com"
    payload = {"email": email, "password": "correct-horse-battery-staple"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_wrong_password_is_rejected(client: AsyncClient):
    email = "wrongpw@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery-staple"})
    login = await client.post("/api/v1/auth/login", data={"username": email, "password": "not-the-right-password"})
    assert login.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_requires_a_token(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
