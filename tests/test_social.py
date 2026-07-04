"""
Social module smoke tests. Actual publishing (services/sync-engine/
adapters/social/meta.py) is untestable end-to-end without a real Meta
access token -- covered here is what's fully local: scheduling and listing
posts through the API.
"""
import uuid
from datetime import UTC, datetime, timedelta

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
            "name": f"Social Test {uuid.uuid4()}",
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
async def test_schedule_and_list_posts(client: AsyncClient):
    business_id, headers = await _signup_owner(client)
    scheduled_at = (datetime.now(UTC) + timedelta(days=1)).isoformat()

    create = await client.post(
        f"/api/v1/businesses/{business_id}/social/posts",
        json={
            "platform": "meta",
            "content": "We're open this weekend!",
            "scheduled_at": scheduled_at,
        },
        headers=headers,
    )
    assert create.status_code == 201, create.text
    assert create.json()["status"] == "pending"

    listing = await client.get(
        f"/api/v1/businesses/{business_id}/social/posts", headers=headers
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1


@pytest.mark.asyncio
async def test_social_posts_require_business_access(client: AsyncClient):
    business_id, _ = await _signup_owner(client)
    _, other_headers = await _signup_owner(client)

    resp = await client.get(
        f"/api/v1/businesses/{business_id}/social/posts", headers=other_headers
    )
    assert resp.status_code == 403
