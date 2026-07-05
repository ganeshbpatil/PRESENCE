"""
Credit-ledger recharge — verifies against a real Razorpay payment rather
than trusting a client-supplied amount (see billing.py:recharge_credit).
This was a real, unguarded revenue-leakage gap (see CLAUDE.md's audit
history): any user with business-write access could previously credit an
arbitrary amount with no payment ever having happened.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

import gateway.api.v1.billing as billing_module
from gateway.config import Settings, get_settings
from gateway.main import app
from shared.models.core import BusinessCategory, BusinessTier


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _force_settings(monkeypatch: pytest.MonkeyPatch, **overrides) -> None:
    forced = Settings(**overrides)
    monkeypatch.setattr(billing_module, "get_settings", lambda: forced)


class _FakeRazorpayClient:
    """Stands in for services.billing.razorpay_client.RazorpayClient so
    tests don't hit the real Razorpay API (untestable here per the client's
    own docstring — no real key/secret in this environment)."""

    def __init__(self, payment: dict | None = None, *_args, **_kwargs):
        self._payment = payment or {"status": "captured", "currency": "INR", "amount": 10000}

    async def fetch_payment(self, razorpay_payment_id: str) -> dict:
        return self._payment


async def _signup_owner(client: AsyncClient) -> tuple[str, dict]:
    biz = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"Recharge Test {uuid.uuid4()}",
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
async def test_recharge_refuses_when_razorpay_not_configured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_settings(monkeypatch, razorpay_key_id="", razorpay_key_secret="")
    business_id, headers = await _signup_owner(client)

    resp = await client.post(
        f"/api/v1/credit-ledger/{business_id}/recharge",
        json={"credit_type": "ai", "razorpay_payment_id": "pay_fake"},
        headers=headers,
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_recharge_credits_exactly_the_captured_razorpay_amount(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_settings(monkeypatch, razorpay_key_id="rzp_test", razorpay_key_secret="secret")
    monkeypatch.setattr(
        billing_module,
        "RazorpayClient",
        lambda *a, **kw: _FakeRazorpayClient(
            {"status": "captured", "currency": "INR", "amount": 10000}  # 100.00 INR in paise
        ),
    )
    business_id, headers = await _signup_owner(client)

    resp = await client.post(
        f"/api/v1/credit-ledger/{business_id}/recharge",
        json={"credit_type": "ai", "razorpay_payment_id": "pay_abc123"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert Decimal(resp.json()["balance"]) == Decimal("100.00")


@pytest.mark.asyncio
async def test_recharge_is_idempotent_on_repeated_payment_id(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_settings(monkeypatch, razorpay_key_id="rzp_test", razorpay_key_secret="secret")
    monkeypatch.setattr(
        billing_module,
        "RazorpayClient",
        lambda *a, **kw: _FakeRazorpayClient(
            {"status": "captured", "currency": "INR", "amount": 5000}
        ),
    )
    business_id, headers = await _signup_owner(client)
    body = {"credit_type": "ai", "razorpay_payment_id": "pay_replayed"}

    first = await client.post(
        f"/api/v1/credit-ledger/{business_id}/recharge", json=body, headers=headers
    )
    second = await client.post(
        f"/api/v1/credit-ledger/{business_id}/recharge", json=body, headers=headers
    )
    assert first.status_code == 200 and second.status_code == 200
    # Same payment ID replayed must not double-credit.
    assert Decimal(first.json()["balance"]) == Decimal("50.00")
    assert Decimal(second.json()["balance"]) == Decimal("50.00")


@pytest.mark.asyncio
async def test_recharge_rejects_uncaptured_payment(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_settings(monkeypatch, razorpay_key_id="rzp_test", razorpay_key_secret="secret")
    monkeypatch.setattr(
        billing_module,
        "RazorpayClient",
        lambda *a, **kw: _FakeRazorpayClient(
            {"status": "created", "currency": "INR", "amount": 10000}
        ),
    )
    business_id, headers = await _signup_owner(client)

    resp = await client.post(
        f"/api/v1/credit-ledger/{business_id}/recharge",
        json={"credit_type": "ai", "razorpay_payment_id": "pay_not_captured"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_recharge_rejects_non_inr_payment(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_settings(monkeypatch, razorpay_key_id="rzp_test", razorpay_key_secret="secret")
    monkeypatch.setattr(
        billing_module,
        "RazorpayClient",
        lambda *a, **kw: _FakeRazorpayClient(
            {"status": "captured", "currency": "USD", "amount": 10000}
        ),
    )
    business_id, headers = await _signup_owner(client)

    resp = await client.post(
        f"/api/v1/credit-ledger/{business_id}/recharge",
        json={"credit_type": "ai", "razorpay_payment_id": "pay_usd"},
        headers=headers,
    )
    assert resp.status_code == 422
