"""
Platform-connection endpoint tests (gateway/api/v1/businesses.py). The
happy path (a real Vault write succeeding) needs a live, unsealed Vault --
out of scope here per test_social.py's precedent for anything requiring a
real external dependency. What's covered locally: no-token connections
skip Vault entirely, and a Vault failure degrades to a clean error instead
of silently persisting a connection with an unretrievable token or
crashing the request (CLAUDE.md principle #1 applied to vault-dependence).
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.config import Settings, get_settings
from gateway.main import app
from shared.models.core import BusinessCategory, BusinessTier


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _signup_owner(client: AsyncClient) -> tuple[str, dict]:
    biz = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"Connection Test {uuid.uuid4()}",
            "category": BusinessCategory.salon_spa_gym.value,
            "tier": BusinessTier.starter.value,
        },
    )
    business_id = biz.json()["id"]
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"owner-{uuid.uuid4()}@example.com",
            "password": "correct-horse-battery",
            "role": "smb_owner",
            "business_id": business_id,
        },
    )
    token = signup.json()["access_token"]
    return business_id, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_connection_without_token_never_touches_vault(client: AsyncClient):
    business_id, headers = await _signup_owner(client)

    resp = await client.post(
        f"/api/v1/businesses/{business_id}/connections",
        json={"platform": "gbp", "external_id": "locations/123"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["last_synced_at"] is None
    assert "access_token" not in resp.json()
    assert "access_token_ref" not in resp.json()


@pytest.mark.asyncio
async def test_connection_with_token_fails_cleanly_when_vault_rejects_credentials(
    client: AsyncClient,
):
    """Force AppRole login to fail (bogus role/secret id) and confirm the
    endpoint returns a clean 502 rather than a 500 or a silently-persisted
    connection with a token nobody can ever retrieve."""
    business_id, headers = await _signup_owner(client)

    def bogus_vault_settings() -> Settings:
        base = get_settings()
        return base.model_copy(
            update={
                "vault_role_id": "definitely-not-a-real-role-id",
                "vault_secret_id": "definitely-not-a-real-secret-id",
            }
        )

    app.dependency_overrides[get_settings] = bogus_vault_settings
    try:
        resp = await client.post(
            f"/api/v1/businesses/{business_id}/connections",
            json={"platform": "meta", "external_id": "page-123", "access_token": "raw-token"},
            headers=headers,
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert resp.status_code == 502, resp.text
