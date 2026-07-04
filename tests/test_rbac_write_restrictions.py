"""
agency_viewer is documented in SECURITY_ARCHITECTURE.md as read-only, but
gateway/tenancy.py's assert_can_access_business previously didn't
distinguish it from agency_admin -- a viewer could send WhatsApp
campaigns, recharge credit, etc. This asserts every write endpoint a
business-scoped viewer can reach now 403s, while reads stay 200.
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.db import async_session_factory
from gateway.main import app
from shared.models.core import (
    Agency,
    Business,
    BusinessCategory,
    BusinessTier,
    PlatformName,
    Review,
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _make_agency_business() -> tuple[uuid.UUID, uuid.UUID]:
    async with async_session_factory() as db:
        agency = Agency(name=f"RBAC Test Agency {uuid.uuid4()}")
        db.add(agency)
        await db.flush()
        business = Business(
            name=f"RBAC Test Business {uuid.uuid4()}",
            category=BusinessCategory.salon_spa_gym,
            tier=BusinessTier.starter,
            agency_id=agency.id,
        )
        db.add(business)
        await db.commit()
        await db.refresh(agency)
        await db.refresh(business)
        return agency.id, business.id


async def _signup(client: AsyncClient, role: str, agency_id: uuid.UUID) -> dict:
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"{role}-{uuid.uuid4()}@example.com",
            "password": "correct-horse-battery",
            "role": role,
            "agency_id": str(agency_id),
        },
    )
    assert signup.status_code == 201, signup.text
    return {"Authorization": f"Bearer {signup.json()['access_token']}"}


async def _make_review(business_id: uuid.UUID) -> uuid.UUID:
    async with async_session_factory() as db:
        review = Review(business_id=business_id, platform=PlatformName.gbp, rating=4, text="fine")
        db.add(review)
        await db.commit()
        await db.refresh(review)
        return review.id


@pytest.mark.asyncio
async def test_agency_viewer_reads_still_work(client: AsyncClient):
    agency_id, business_id = await _make_agency_business()
    headers = await _signup(client, "agency_viewer", agency_id)

    biz_get = await client.get(f"/api/v1/businesses/{business_id}", headers=headers)
    assert biz_get.status_code == 200
    conn_get = await client.get(
        f"/api/v1/businesses/{business_id}/connections/health", headers=headers
    )
    assert conn_get.status_code == 200
    reviews_get = await client.get(f"/api/v1/businesses/{business_id}/reviews", headers=headers)
    assert reviews_get.status_code == 200
    balance_get = await client.get(f"/api/v1/credit-ledger/{business_id}/balance", headers=headers)
    assert balance_get.status_code == 200
    agency_get = await client.get(f"/api/v1/agencies/{agency_id}/businesses", headers=headers)
    assert agency_get.status_code == 200


@pytest.mark.asyncio
async def test_agency_viewer_cannot_create_connection(client: AsyncClient):
    agency_id, business_id = await _make_agency_business()
    headers = await _signup(client, "agency_viewer", agency_id)
    resp = await client.post(
        f"/api/v1/businesses/{business_id}/connections", json={"platform": "gbp"}, headers=headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agency_viewer_cannot_create_subscription(client: AsyncClient):
    agency_id, business_id = await _make_agency_business()
    headers = await _signup(client, "agency_viewer", agency_id)
    resp = await client.post(
        "/api/v1/billing/subscriptions",
        json={"business_id": str(business_id), "plan_id": "plan_test"},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agency_viewer_cannot_recharge_credit(client: AsyncClient):
    agency_id, business_id = await _make_agency_business()
    headers = await _signup(client, "agency_viewer", agency_id)
    resp = await client.post(
        f"/api/v1/credit-ledger/{business_id}/recharge",
        json={"credit_type": "ai", "razorpay_payment_id": "pay_test123"},
        headers=headers,
    )
    # RBAC is enforced before the Razorpay lookup ever happens, so a fake
    # payment ID is fine here -- this is testing the 403, not payment
    # verification.
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agency_viewer_cannot_create_contact(client: AsyncClient):
    agency_id, business_id = await _make_agency_business()
    headers = await _signup(client, "agency_viewer", agency_id)
    resp = await client.post(
        "/api/v1/contacts",
        json={"business_id": str(business_id), "phone_e164": "+911234567890"},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agency_viewer_cannot_create_campaign(client: AsyncClient):
    agency_id, business_id = await _make_agency_business()
    headers = await _signup(client, "agency_viewer", agency_id)
    resp = await client.post(
        "/api/v1/campaigns",
        json={
            "business_id": str(business_id),
            "name": "Test Campaign",
            "template_name": "greeting",
            "category": "utility",
        },
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agency_viewer_cannot_create_review(client: AsyncClient):
    agency_id, business_id = await _make_agency_business()
    headers = await _signup(client, "agency_viewer", agency_id)
    resp = await client.post(
        f"/api/v1/businesses/{business_id}/reviews", json={"platform": "gbp"}, headers=headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agency_viewer_cannot_draft_or_send_response(client: AsyncClient):
    agency_id, business_id = await _make_agency_business()
    review_id = await _make_review(business_id)
    headers = await _signup(client, "agency_viewer", agency_id)

    draft = await client.post(f"/api/v1/reviews/{review_id}/draft-response", headers=headers)
    assert draft.status_code == 403

    send = await client.post(f"/api/v1/reviews/{review_id}/send-response", headers=headers)
    assert send.status_code == 403


@pytest.mark.asyncio
async def test_agency_viewer_cannot_schedule_post(client: AsyncClient):
    agency_id, business_id = await _make_agency_business()
    headers = await _signup(client, "agency_viewer", agency_id)
    resp = await client.post(
        f"/api/v1/businesses/{business_id}/social/posts",
        json={
            "platform": "meta",
            "content": "hello",
            "scheduled_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agency_viewer_cannot_trigger_attribution(client: AsyncClient):
    agency_id, business_id = await _make_agency_business()
    headers = await _signup(client, "agency_viewer", agency_id)
    now = datetime.now(UTC)
    resp = await client.post(
        "/api/v1/attribution/compute-correlation",
        json={
            "business_id": str(business_id),
            "period_start": (now - timedelta(days=7)).isoformat(),
            "period_end": now.isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agency_admin_can_still_write(client: AsyncClient):
    """Sanity check the fix doesn't overreach and block agency_admin too."""
    agency_id, business_id = await _make_agency_business()
    headers = await _signup(client, "agency_admin", agency_id)
    resp = await client.post(
        f"/api/v1/businesses/{business_id}/reviews", json={"platform": "gbp"}, headers=headers
    )
    assert resp.status_code == 201, resp.text
