"""
Razorpay webhook signature verification — high rigor per
TESTING_STRATEGY.md's billing carve-out. Covers both the pure HMAC helper
and the HTTP endpoint's reject-before-processing behavior, per
SECURITY_ARCHITECTURE.md's non-negotiable webhook verification rule.
"""
import hashlib
import hmac
import json

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.main import app
from services.billing.razorpay_client import verify_webhook_signature


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_verify_webhook_signature_accepts_valid_signature():
    body = b'{"event": "subscription.charged"}'
    secret = "test-webhook-secret"
    assert verify_webhook_signature(body, _sign(body, secret), secret) is True


def test_verify_webhook_signature_rejects_tampered_body():
    body = b'{"event": "subscription.charged"}'
    secret = "test-webhook-secret"
    signature = _sign(body, secret)
    tampered = b'{"event": "subscription.cancelled"}'
    assert verify_webhook_signature(tampered, signature, secret) is False


def test_verify_webhook_signature_rejects_wrong_secret():
    body = b'{"event": "subscription.charged"}'
    signature = _sign(body, "correct-secret")
    assert verify_webhook_signature(body, signature, "wrong-secret") is False


def test_verify_webhook_signature_rejects_missing_signature():
    body = b'{"event": "subscription.charged"}'
    assert verify_webhook_signature(body, "", "some-secret") is False


@pytest.mark.asyncio
async def test_razorpay_webhook_endpoint_rejects_unsigned_payload():
    transport = ASGITransport(app=app)
    payload = {"event": "subscription.charged", "payload": {}}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/webhooks/razorpay",
            content=json.dumps(payload),
            headers={"X-Razorpay-Signature": "not-a-real-signature"},
        )
    # RAZORPAY_WEBHOOK_SECRET is blank in this environment's .env, so
    # verify_webhook_signature() short-circuits to False regardless of the
    # header value -- proving the endpoint never reaches event-processing
    # logic without a verified signature.
    assert resp.status_code == 401
