"""POST /agencies + PATCH /agencies/{id}."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.config import get_settings
from gateway.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _create_agency(client: AsyncClient, **overrides) -> str:
    body = {
        "name": f"New Agency {uuid.uuid4()}",
        "invite_code": get_settings().signup_invite_code,
        **overrides,
    }
    resp = await client.post("/api/v1/agencies", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _signup_admin(client: AsyncClient, agency_id: str) -> dict:
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"admin-{uuid.uuid4()}@example.com",
            "password": "correct-horse-battery",
            "role": "agency_admin",
            "agency_id": agency_id,
        },
    )
    assert signup.status_code == 201, signup.text
    return {"Authorization": f"Bearer {signup.json()['access_token']}"}


@pytest.mark.asyncio
async def test_create_agency_returns_expected_shape(client: AsyncClient):
    resp = await client.post(
        "/api/v1/agencies",
        json={
            "name": "Test Agency Co",
            "is_white_label": True,
            "revenue_share_pct": "12.50",
            "invite_code": get_settings().signup_invite_code,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Test Agency Co"
    assert body["is_white_label"] is True
    assert body["revenue_share_pct"] == "12.50"
    assert body["branding_config"] is None


@pytest.mark.asyncio
async def test_agency_admin_can_edit_own_agency(client: AsyncClient):
    agency_id = await _create_agency(client)
    headers = await _signup_admin(client, agency_id)

    resp = await client.patch(
        f"/api/v1/agencies/{agency_id}",
        json={"name": "Renamed Agency", "branding_config": {"logo_url": "https://x/y.png"}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Renamed Agency"
    assert body["branding_config"] == {"logo_url": "https://x/y.png"}


@pytest.mark.asyncio
async def test_partial_agency_update_leaves_other_fields_untouched(client: AsyncClient):
    agency_id = await _create_agency(client, is_white_label=True)
    headers = await _signup_admin(client, agency_id)

    resp = await client.patch(
        f"/api/v1/agencies/{agency_id}", json={"revenue_share_pct": "20.00"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["revenue_share_pct"] == "20.00"
    assert body["is_white_label"] is True


@pytest.mark.asyncio
async def test_cannot_edit_a_different_agency(client: AsyncClient):
    agency_id = await _create_agency(client)
    other_agency_id = await _create_agency(client)
    headers = await _signup_admin(client, agency_id)

    resp = await client.patch(
        f"/api/v1/agencies/{other_agency_id}", json={"name": "Hijacked"}, headers=headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agency_viewer_cannot_edit_agency(client: AsyncClient):
    agency_id = await _create_agency(client)
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"viewer-{uuid.uuid4()}@example.com",
            "password": "correct-horse-battery",
            "role": "agency_viewer",
            "agency_id": agency_id,
        },
    )
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    resp = await client.patch(
        f"/api/v1/agencies/{agency_id}", json={"name": "Nope"}, headers=headers
    )
    assert resp.status_code == 403
