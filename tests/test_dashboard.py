"""GET /businesses/{id}/dashboard and GET /agencies/{id}/dashboard."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.config import get_settings
from gateway.db import async_session_factory
from gateway.main import app
from shared.models.core import Review


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
            "invite_code": get_settings().signup_invite_code,
        },
    )
    assert signup.status_code == 201, signup.text
    return {"Authorization": f"Bearer {signup.json()['access_token']}"}


async def _create_business(client: AsyncClient, headers: dict, agency_id: str) -> str:
    resp = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"Business {uuid.uuid4()}",
            "category": "salon_spa_gym",
            "tier": "starter",
            "agency_id": agency_id,
            "invite_code": get_settings().signup_invite_code,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_review(
    client: AsyncClient, headers: dict, business_id: str, rating: int, respond: bool = False
) -> str:
    resp = await client.post(
        f"/api/v1/businesses/{business_id}/reviews",
        json={"platform": "gbp", "rating": rating, "text": "test review"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    review_id = resp.json()["id"]
    if respond:
        draft = await client.post(f"/api/v1/reviews/{review_id}/draft-response", headers=headers)
        # AI keys are placeholders in this environment -- draft may 502, in
        # which case we set response_sent_at directly for the fixture instead
        # of routing every test through a real AI provider call.
        if draft.status_code != 200:
            async with async_session_factory() as db:
                review = await db.get(Review, uuid.UUID(review_id))
                review.ai_drafted_response = "canned response"
                review.response_sent_at = datetime.now(UTC)
                await db.commit()
        else:
            await client.post(f"/api/v1/reviews/{review_id}/send-response", headers=headers)
    return review_id


@pytest.mark.asyncio
async def test_business_dashboard_shape_with_no_reviews(client: AsyncClient):
    agency_id = await _create_agency(client)
    headers = await _signup_admin(client, agency_id)
    business_id = await _create_business(client, headers, agency_id)

    resp = await client.get(f"/api/v1/businesses/{business_id}/dashboard", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["business_id"] == business_id
    assert body["avg_rating"] is None
    assert body["reviews_this_month"] == 0
    assert body["pending_replies"] == 0
    assert body["reply_rate_pct"] is None
    assert len(body["review_volume"]) == 30
    assert len(body["rating_distribution"]) == 5
    assert all(b["count"] == 0 for b in body["rating_distribution"])


@pytest.mark.asyncio
async def test_business_dashboard_computes_real_kpis(client: AsyncClient):
    agency_id = await _create_agency(client)
    headers = await _signup_admin(client, agency_id)
    business_id = await _create_business(client, headers, agency_id)

    await _create_review(client, headers, business_id, rating=5, respond=True)
    await _create_review(client, headers, business_id, rating=3)
    await _create_review(client, headers, business_id, rating=1)

    resp = await client.get(f"/api/v1/businesses/{business_id}/dashboard", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["avg_rating"] == pytest.approx(3.0)
    assert body["reviews_this_month"] == 3
    assert body["pending_replies"] == 2
    assert body["reply_rate_pct"] == pytest.approx(100 / 3)

    ratings = {b["rating"]: b["count"] for b in body["rating_distribution"]}
    assert ratings == {1: 1, 2: 0, 3: 1, 4: 0, 5: 1}

    today = datetime.now(UTC).date().isoformat()
    today_point = next(p for p in body["review_volume"] if p["date"] == today)
    assert today_point["count"] == 3


@pytest.mark.asyncio
async def test_agency_dashboard_aggregates_across_businesses_and_counts_active(
    client: AsyncClient,
):
    agency_id = await _create_agency(client)
    headers = await _signup_admin(client, agency_id)
    b1 = await _create_business(client, headers, agency_id)
    b2 = await _create_business(client, headers, agency_id)

    await _create_review(client, headers, b1, rating=4)
    await _create_review(client, headers, b2, rating=2)

    resp = await client.get(f"/api/v1/agencies/{agency_id}/dashboard", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["agency_id"] == agency_id
    assert body["total_businesses"] == 2
    assert body["active_businesses"] == 2
    assert body["avg_rating"] == pytest.approx(3.0)
    assert body["reviews_this_month"] == 2


@pytest.mark.asyncio
async def test_agency_dashboard_with_no_businesses_returns_empty_shape(client: AsyncClient):
    agency_id = await _create_agency(client)
    headers = await _signup_admin(client, agency_id)

    resp = await client.get(f"/api/v1/agencies/{agency_id}/dashboard", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_businesses"] == 0
    assert body["active_businesses"] == 0
    assert body["avg_rating"] is None
    assert len(body["review_volume"]) == 30


@pytest.mark.asyncio
async def test_cannot_read_a_different_businesss_dashboard(client: AsyncClient):
    agency_id = await _create_agency(client)
    other_agency_id = await _create_agency(client)
    headers = await _signup_admin(client, agency_id)
    other_headers = await _signup_admin(client, other_agency_id)
    business_id = await _create_business(client, headers, agency_id)

    resp = await client.get(
        f"/api/v1/businesses/{business_id}/dashboard", headers=other_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cannot_read_a_different_agencys_dashboard(client: AsyncClient):
    agency_id = await _create_agency(client)
    other_agency_id = await _create_agency(client)
    headers = await _signup_admin(client, other_agency_id)

    resp = await client.get(f"/api/v1/agencies/{agency_id}/dashboard", headers=headers)
    assert resp.status_code == 403
