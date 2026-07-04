"""PATCH /businesses/{id} -- edit a business after creation."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.config import get_settings
from gateway.db import async_session_factory
from gateway.main import app
from shared.models.core import Agency, Business, BusinessCategory, BusinessTier


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _signup_owner(client: AsyncClient) -> tuple[str, dict]:
    biz = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"Edit Test {uuid.uuid4()}",
            "category": BusinessCategory.salon_spa_gym.value,
            "tier": BusinessTier.starter.value,
            "invite_code": get_settings().signup_invite_code,
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
async def test_owner_can_update_own_business(client: AsyncClient):
    business_id, headers = await _signup_owner(client)

    resp = await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={"name": "Renamed Salon", "area": "Koregaon Park"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Renamed Salon"
    assert body["area"] == "Koregaon Park"
    # untouched fields stay as they were
    assert body["category"] == BusinessCategory.salon_spa_gym.value


@pytest.mark.asyncio
async def test_partial_update_leaves_other_fields_untouched(client: AsyncClient):
    business_id, headers = await _signup_owner(client)

    resp = await client.patch(
        f"/api/v1/businesses/{business_id}", json={"pincode": "411001"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["pincode"] == "411001"
    assert body["name"].startswith("Edit Test")


@pytest.mark.asyncio
async def test_agency_id_is_not_editable_via_this_endpoint(client: AsyncClient):
    business_id, headers = await _signup_owner(client)

    other_agency_id = str(uuid.uuid4())
    resp = await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={"name": "Still Renamed", "agency_id": other_agency_id},
        headers=headers,
    )
    # agency_id isn't a field on BusinessUpdate -- FastAPI/Pydantic ignores
    # unknown keys by default, so this must succeed but NOT reassign agency.
    assert resp.status_code == 200, resp.text
    assert resp.json()["agency_id"] is None


@pytest.mark.asyncio
async def test_cannot_update_a_business_outside_your_scope(client: AsyncClient):
    _own_business_id, headers = await _signup_owner(client)
    other_business_id, _other_headers = await _signup_owner(client)

    resp = await client.patch(
        f"/api/v1/businesses/{other_business_id}",
        json={"name": "Hijacked"},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agency_viewer_cannot_update_business(client: AsyncClient):
    async with async_session_factory() as db:
        agency = Agency(name=f"Edit RBAC Agency {uuid.uuid4()}")
        db.add(agency)
        await db.flush()
        business = Business(
            name=f"Edit RBAC Business {uuid.uuid4()}",
            category=BusinessCategory.salon_spa_gym,
            tier=BusinessTier.starter,
            agency_id=agency.id,
        )
        db.add(business)
        await db.commit()
        await db.refresh(agency)
        await db.refresh(business)

    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"viewer-{uuid.uuid4()}@example.com",
            "password": "correct-horse-battery",
            "role": "agency_viewer",
            "agency_id": str(agency.id),
        },
    )
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    resp = await client.patch(
        f"/api/v1/businesses/{business.id}", json={"name": "Nope"}, headers=headers
    )
    assert resp.status_code == 403
