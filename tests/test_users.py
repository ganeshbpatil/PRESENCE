"""
PATCH /users/{id} + the two list endpoints. The escalation guards here are
the highest-risk logic in the whole write-console plan: no self-role-edit,
no smb_owner granting agency roles, no reassigning a user into a scope the
caller doesn't control.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.db import async_session_factory
from gateway.main import app
from shared.models.core import Agency, Business, BusinessCategory, BusinessTier


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _make_agency() -> uuid.UUID:
    async with async_session_factory() as db:
        agency = Agency(name=f"Users Test Agency {uuid.uuid4()}")
        db.add(agency)
        await db.commit()
        await db.refresh(agency)
        return agency.id


async def _make_business(agency_id: uuid.UUID | None = None) -> uuid.UUID:
    async with async_session_factory() as db:
        business = Business(
            name=f"Users Test Business {uuid.uuid4()}",
            category=BusinessCategory.salon_spa_gym,
            tier=BusinessTier.starter,
            agency_id=agency_id,
        )
        db.add(business)
        await db.commit()
        await db.refresh(business)
        return business.id


async def _signup(client: AsyncClient, role: str, **scope) -> tuple[dict, dict]:
    """Returns (headers, user_summary_including_id)."""
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"{role}-{uuid.uuid4()}@example.com",
            "password": "correct-horse-battery",
            "role": role,
            **scope,
        },
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    return headers, me.json()


@pytest.mark.asyncio
async def test_list_business_users(client: AsyncClient):
    business_id = await _make_business()
    headers, owner = await _signup(client, "smb_owner", business_id=str(business_id))

    resp = await client.get(f"/api/v1/businesses/{business_id}/users", headers=headers)
    assert resp.status_code == 200, resp.text
    ids = [u["id"] for u in resp.json()]
    assert owner["id"] in ids


@pytest.mark.asyncio
async def test_list_agency_users(client: AsyncClient):
    agency_id = await _make_agency()
    headers, admin = await _signup(client, "agency_admin", agency_id=str(agency_id))

    resp = await client.get(f"/api/v1/agencies/{agency_id}/users", headers=headers)
    assert resp.status_code == 200, resp.text
    ids = [u["id"] for u in resp.json()]
    assert admin["id"] in ids


@pytest.mark.asyncio
async def test_agency_admin_can_deactivate_business_user_in_their_agency(client: AsyncClient):
    agency_id = await _make_agency()
    business_id = await _make_business(agency_id)
    admin_headers, _admin = await _signup(client, "agency_admin", agency_id=str(agency_id))
    _owner_headers, owner = await _signup(client, "smb_owner", business_id=str(business_id))

    resp = await client.patch(
        f"/api/v1/users/{owner['id']}", json={"is_active": False}, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_smb_owner_cannot_grant_agency_admin_role_to_a_peer(client: AsyncClient):
    business_id = await _make_business()
    owner_headers, _owner = await _signup(client, "smb_owner", business_id=str(business_id))
    _peer_headers, peer = await _signup(client, "smb_owner", business_id=str(business_id))

    resp = await client.patch(
        f"/api/v1/users/{peer['id']}", json={"role": "agency_admin"}, headers=owner_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cannot_self_escalate_role(client: AsyncClient):
    agency_id = await _make_agency()
    admin_headers, admin = await _signup(client, "agency_admin", agency_id=str(agency_id))

    resp = await client.patch(
        f"/api/v1/users/{admin['id']}", json={"role": "agency_viewer"}, headers=admin_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cannot_self_deactivate(client: AsyncClient):
    business_id = await _make_business()
    owner_headers, owner = await _signup(client, "smb_owner", business_id=str(business_id))

    resp = await client.patch(
        f"/api/v1/users/{owner['id']}", json={"is_active": False}, headers=owner_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cannot_reassign_user_into_a_foreign_agency(client: AsyncClient):
    agency_a = await _make_agency()
    agency_b = await _make_agency()
    business_a = await _make_business(agency_a)
    admin_a_headers, _admin_a = await _signup(client, "agency_admin", agency_id=str(agency_a))
    _owner_headers, owner = await _signup(client, "smb_owner", business_id=str(business_a))

    resp = await client.patch(
        f"/api/v1/users/{owner['id']}",
        json={"agency_id": str(agency_b)},
        headers=admin_a_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agency_viewer_cannot_edit_users(client: AsyncClient):
    agency_id = await _make_agency()
    business_id = await _make_business(agency_id)
    viewer_headers, _viewer = await _signup(client, "agency_viewer", agency_id=str(agency_id))
    _owner_headers, owner = await _signup(client, "smb_owner", business_id=str(business_id))

    resp = await client.patch(
        f"/api/v1/users/{owner['id']}", json={"is_active": False}, headers=viewer_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agency_admin_can_reassign_user_within_own_agency(client: AsyncClient):
    agency_id = await _make_agency()
    business_a = await _make_business(agency_id)
    business_b = await _make_business(agency_id)
    admin_headers, _admin = await _signup(client, "agency_admin", agency_id=str(agency_id))
    _owner_headers, owner = await _signup(client, "smb_owner", business_id=str(business_a))

    resp = await client.patch(
        f"/api/v1/users/{owner['id']}",
        json={"business_id": str(business_b)},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["business_id"] == str(business_b)
