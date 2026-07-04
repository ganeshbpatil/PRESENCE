"""
Notifications smoke tests. Covers the in-app channel end-to-end (creating
a review fires review.received -> a NotificationEntry the owner can list
and mark read). Email delivery isn't asserted here beyond "doesn't raise"
-- SMTP_HOST is blank in this environment's .env, so send_email() takes
the logging fallback rather than actually sending.
"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

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
            "name": f"Notif Test {uuid.uuid4()}",
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
async def test_review_received_creates_and_lists_notification(client: AsyncClient):
    business_id, headers = await _signup_owner(client)

    review = await client.post(
        f"/api/v1/businesses/{business_id}/reviews",
        json={"platform": "gbp", "rating": 4, "text": "Pretty good!"},
        headers=headers,
    )
    assert review.status_code == 201, review.text

    listing = await client.get("/api/v1/notifications", headers=headers)
    assert listing.status_code == 200
    notifications = listing.json()
    assert len(notifications) == 1
    assert notifications[0]["event_type"] == "review.received"
    assert notifications[0]["read_at"] is None


@pytest.mark.asyncio
async def test_mark_notification_read(client: AsyncClient):
    business_id, headers = await _signup_owner(client)
    await client.post(
        f"/api/v1/businesses/{business_id}/reviews",
        json={"platform": "gbp", "rating": 5, "text": "Great!"},
        headers=headers,
    )

    listing = await client.get("/api/v1/notifications", headers=headers)
    notification_id = listing.json()[0]["id"]

    read = await client.post(f"/api/v1/notifications/{notification_id}/read", headers=headers)
    assert read.status_code == 200
    assert read.json()["read_at"] is not None


@pytest.mark.asyncio
async def test_cannot_read_another_businesss_notification(client: AsyncClient):
    business_id, headers = await _signup_owner(client)
    _, other_headers = await _signup_owner(client)

    await client.post(
        f"/api/v1/businesses/{business_id}/reviews",
        json={"platform": "gbp", "rating": 3, "text": "Okay."},
        headers=headers,
    )
    listing = await client.get("/api/v1/notifications", headers=headers)
    notification_id = listing.json()[0]["id"]

    resp = await client.post(
        f"/api/v1/notifications/{notification_id}/read", headers=other_headers
    )
    assert resp.status_code == 403
