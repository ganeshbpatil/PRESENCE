"""Agency console smoke tests: agency-scoped business list + CSV report."""
import csv
import io
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.db import async_session_factory
from gateway.main import app
from shared.models.core import Agency, BusinessCategory, BusinessTier


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _make_agency() -> uuid.UUID:
    async with async_session_factory() as db:
        agency = Agency(name=f"Test Agency {uuid.uuid4()}")
        db.add(agency)
        await db.commit()
        await db.refresh(agency)
        return agency.id


@pytest.mark.asyncio
async def test_agency_admin_can_list_and_export_businesses(client: AsyncClient):
    agency_id = await _make_agency()

    biz = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"Agency Client {uuid.uuid4()}",
            "category": BusinessCategory.fnb.value,
            "tier": BusinessTier.growth.value,
            "agency_id": str(agency_id),
        },
    )
    assert biz.status_code == 201, biz.text

    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"agency-admin-{uuid.uuid4()}@example.com",
            "password": "correct-horse-battery",
            "role": "agency_admin",
            "agency_id": str(agency_id),
        },
    )
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    listing = await client.get(f"/api/v1/agencies/{agency_id}/businesses", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    report = await client.get(f"/api/v1/agencies/{agency_id}/consolidated-report", headers=headers)
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(report.text)))
    assert rows[0][0] == "business_id"
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_smb_owner_cannot_access_agency_console(client: AsyncClient):
    agency_id = await _make_agency()
    biz = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"Owner Biz {uuid.uuid4()}",
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
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    resp = await client.get(f"/api/v1/agencies/{agency_id}/businesses", headers=headers)
    assert resp.status_code == 403
