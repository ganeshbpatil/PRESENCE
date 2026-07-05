"""
Reviews + AI draft-response tests. The actual AI provider call is
untestable end-to-end here (OPENROUTER_API_KEY/ANTHROPIC_API_KEY are
placeholders in this environment's .env) -- these tests cover what IS
fully exercisable: credit pre-flight checks, the refund-on-failure path,
and the draft-then-approve gate (never auto-send).
"""
import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.config import get_settings
from gateway.db import async_session_factory
from gateway.main import app
from services.billing import credit_ledger
from shared.models.core import BusinessCategory, BusinessTier, CreditType


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _signup_owner(client: AsyncClient) -> tuple[str, dict]:
    biz = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"Review Test {uuid.uuid4()}",
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


async def _create_review(client: AsyncClient, business_id: str, headers: dict) -> str:
    resp = await client.post(
        f"/api/v1/businesses/{business_id}/reviews",
        json={"platform": "gbp", "rating": 5, "text": "Loved it!"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_draft_response_without_credit_returns_402(client: AsyncClient):
    business_id, headers = await _signup_owner(client)
    review_id = await _create_review(client, business_id, headers)

    resp = await client.post(f"/api/v1/reviews/{review_id}/draft-response", headers=headers)
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_draft_response_failure_refunds_credit(client: AsyncClient):
    business_id, headers = await _signup_owner(client)
    review_id = await _create_review(client, business_id, headers)

    # Seed credit directly through the ledger service rather than the HTTP
    # recharge endpoint -- that endpoint now requires a real captured
    # Razorpay payment to verify against (see billing.py:recharge_credit),
    # which isn't available in this test environment. Going straight
    # through credit_ledger.credit() is the same thing the endpoint itself
    # does internally once a payment is verified.
    async with async_session_factory() as db:
        await credit_ledger.credit(
            db, uuid.UUID(business_id), CreditType.ai, Decimal("1.00"), reference_type="test_seed"
        )
        await db.commit()

    # No real OPENROUTER_API_KEY/ANTHROPIC_API_KEY configured -> the
    # provider call fails and the pre-flight debit must be refunded.
    resp = await client.post(f"/api/v1/reviews/{review_id}/draft-response", headers=headers)
    assert resp.status_code == 502

    async with async_session_factory() as db:
        balance = await credit_ledger.get_balance(db, uuid.UUID(business_id), CreditType.ai)
        assert balance == Decimal("1.00")  # fully refunded, not partially


@pytest.mark.asyncio
async def test_send_response_requires_a_draft_first(client: AsyncClient):
    business_id, headers = await _signup_owner(client)
    review_id = await _create_review(client, business_id, headers)

    resp = await client.post(f"/api/v1/reviews/{review_id}/send-response", headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_response_is_a_distinct_approval_step_and_not_repeatable(client: AsyncClient):
    business_id, headers = await _signup_owner(client)
    review_id = await _create_review(client, business_id, headers)

    async with async_session_factory() as db:
        from sqlalchemy import select

        from shared.models.core import Review

        review = (
            await db.execute(select(Review).where(Review.id == uuid.UUID(review_id)))
        ).scalar_one()
        review.ai_drafted_response = "Thanks so much for the kind words!"
        await db.commit()

    first = await client.post(f"/api/v1/reviews/{review_id}/send-response", headers=headers)
    assert first.status_code == 200
    assert first.json()["response_sent_at"] is not None

    second = await client.post(f"/api/v1/reviews/{review_id}/send-response", headers=headers)
    assert second.status_code == 409
