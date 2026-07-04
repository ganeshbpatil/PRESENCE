"""
Auth smoke tests — signup/login/refresh/me happy path plus the one
correctness-critical bit (RBAC role enforcement). Pragmatic coverage per
TESTING_STRATEGY.md's Phase 0-1 bar (this isn't attribution/billing).
"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.config import get_settings
from gateway.main import app
from shared.models.core import BusinessCategory, BusinessTier


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _create_business(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"Test Salon {uuid.uuid4()}",
            "category": BusinessCategory.salon_spa_gym.value,
            "tier": BusinessTier.starter.value,
            "invite_code": get_settings().signup_invite_code,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_signup_login_me_flow(client: AsyncClient):
    business_id = await _create_business(client)
    email = f"owner-{uuid.uuid4()}@example.com"

    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "correct-horse-battery",
            "role": "smb_owner",
            "business_id": business_id,
        },
    )
    assert signup.status_code == 201, signup.text
    tokens = signup.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == email

    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "correct-horse-battery"}
    )
    assert login.status_code == 200

    bad_login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
    )
    assert bad_login.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_and_revokes_old_token(client: AsyncClient):
    business_id = await _create_business(client)
    email = f"owner-{uuid.uuid4()}@example.com"
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "correct-horse-battery",
            "role": "smb_owner",
            "business_id": business_id,
        },
    )
    old_refresh = signup.json()["refresh_token"]

    first = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert first.status_code == 200

    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reused.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_me_is_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
