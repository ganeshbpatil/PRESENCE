"""
services/billing/razorpay_client.py

Thin httpx wrapper around Razorpay's REST API — decision locked during the
LocalEdge exploration, do not re-evaluate PGs (CLAUDE.md). Scope is
subscription billing + credit recharge ONLY; commission/embedded payment
collection on businesses' behalf is explicitly deferred per
06_MODULES/PAYMENTS.md (RBI PA/PG compliance surface, pre-PMF).

Untestable end-to-end in this environment without a real RAZORPAY_KEY_ID/
RAZORPAY_KEY_SECRET — the HTTP contract below matches Razorpay's published
API, but calls will fail against the placeholder .env credentials.
"""
from __future__ import annotations

import hashlib
import hmac

import httpx

_BASE_URL = "https://api.razorpay.com/v1"


class RazorpayError(Exception):
    pass


class RazorpayClient:
    def __init__(self, key_id: str, key_secret: str):
        self._key_id = key_id
        self._key_secret = key_secret

    async def create_subscription(
        self, plan_id: str, total_count: int, customer_notify: bool = True
    ) -> dict:
        async with httpx.AsyncClient(
            base_url=_BASE_URL, auth=(self._key_id, self._key_secret), timeout=10.0
        ) as client:
            resp = await client.post(
                "/subscriptions",
                json={
                    "plan_id": plan_id,
                    "customer_notify": 1 if customer_notify else 0,
                    "total_count": total_count,
                },
            )
        if resp.status_code >= 300:
            raise RazorpayError(
                f"Razorpay create_subscription failed: {resp.status_code} {resp.text}"
            )
        return resp.json()

    async def fetch_subscription(self, razorpay_subscription_id: str) -> dict:
        async with httpx.AsyncClient(
            base_url=_BASE_URL, auth=(self._key_id, self._key_secret), timeout=10.0
        ) as client:
            resp = await client.get(f"/subscriptions/{razorpay_subscription_id}")
        if resp.status_code >= 300:
            raise RazorpayError(
                f"Razorpay fetch_subscription failed: {resp.status_code} {resp.text}"
            )
        return resp.json()

    async def fetch_payment(self, razorpay_payment_id: str) -> dict:
        """Used to verify a credit-ledger recharge against Razorpay's own
        record of the payment (status, amount, currency) rather than
        trusting a client-supplied amount — see billing.py's recharge_credit."""
        async with httpx.AsyncClient(
            base_url=_BASE_URL, auth=(self._key_id, self._key_secret), timeout=10.0
        ) as client:
            resp = await client.get(f"/payments/{razorpay_payment_id}")
        if resp.status_code >= 300:
            raise RazorpayError(
                f"Razorpay fetch_payment failed: {resp.status_code} {resp.text}"
            )
        return resp.json()


def verify_webhook_signature(raw_body: bytes, signature: str, webhook_secret: str) -> bool:
    """Constant-time HMAC-SHA256 verification per Razorpay's webhook docs.
    MUST be called before any webhook payload is trusted/processed — see
    SECURITY_ARCHITECTURE.md's non-negotiable webhook-verification rule."""
    if not signature or not webhook_secret:
        return False
    expected = hmac.new(webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
