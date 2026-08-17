"""Project creation, listing, ownership isolation."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_project(client: AsyncClient, test_user_and_token: dict):
    headers = test_user_and_token["headers"]
    payload = {
        "name": "URL Shortener SaaS",
        "requirement": "Build a URL shortening SaaS with authentication, analytics, PostgreSQL and a React dashboard.",
        "token_budget": 200_000,
    }
    create = await client.post("/api/v1/projects", json=payload, headers=headers)
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["name"] == payload["name"]
    assert body["status"] == "draft"

    get = await client.get(f"/api/v1/projects/{body['id']}", headers=headers)
    assert get.status_code == 200
    assert get.json()["id"] == body["id"]


@pytest.mark.asyncio
async def test_list_projects_only_returns_the_caller_s_own(client: AsyncClient):
    async def register_and_create(email: str) -> dict:
        password = "correct-horse-battery-staple"
        await client.post("/api/v1/auth/register", json={"email": email, "password": password})
        login = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        await client.post(
            "/api/v1/projects", json={"name": f"Project for {email}", "requirement": "Build something useful for testing."},
            headers=headers,
        )
        return headers

    headers_a = await register_and_create("owner-a@example.com")
    headers_b = await register_and_create("owner-b@example.com")

    list_a = await client.get("/api/v1/projects", headers=headers_a)
    list_b = await client.get("/api/v1/projects", headers=headers_b)

    assert len(list_a.json()) == 1
    assert len(list_b.json()) == 1
    assert list_a.json()[0]["name"] == "Project for owner-a@example.com"
    assert list_b.json()[0]["name"] == "Project for owner-b@example.com"


@pytest.mark.asyncio
async def test_cannot_access_another_user_s_project(client: AsyncClient):
    password = "correct-horse-battery-staple"

    await client.post("/api/v1/auth/register", json={"email": "victim@example.com", "password": password})
    login_victim = await client.post("/api/v1/auth/login", data={"username": "victim@example.com", "password": password})
    victim_headers = {"Authorization": f"Bearer {login_victim.json()['access_token']}"}
    create = await client.post(
        "/api/v1/projects", json={"name": "Private Project", "requirement": "Something the attacker should not see."},
        headers=victim_headers,
    )
    project_id = create.json()["id"]

    await client.post("/api/v1/auth/register", json={"email": "attacker@example.com", "password": password})
    login_attacker = await client.post("/api/v1/auth/login", data={"username": "attacker@example.com", "password": password})
    attacker_headers = {"Authorization": f"Bearer {login_attacker.json()['access_token']}"}

    response = await client.get(f"/api/v1/projects/{project_id}", headers=attacker_headers)
    assert response.status_code == 404  # not 403 - existence of another user's project is not confirmed either


@pytest.mark.asyncio
async def test_project_requires_authentication(client: AsyncClient):
    response = await client.post("/api/v1/projects", json={"name": "X", "requirement": "Y" * 20})
    assert response.status_code == 401
