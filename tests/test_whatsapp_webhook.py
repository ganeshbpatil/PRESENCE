"""
Gallabox webhook — fixture-based per BACKEND_STANDARDS.md's adapter-testing
requirement. Covers signature verification reject/accept and the two
payload shapes (inbound message opens the service window; delivery-status
update reaches the matching CampaignMessage) without exercising a live
send (no real GALLABOX_API_KEY in this environment).
"""
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from gateway.config import get_settings
from gateway.db import async_session_factory
from gateway.main import app
from shared.models.core import (
    Business,
    BusinessCategory,
    BusinessTier,
    Campaign,
    CampaignMessage,
    WhatsAppContact,
)

_TEST_WEBHOOK_SECRET = "test-gallabox-webhook-secret"


def _sign(body: bytes) -> str:
    return hmac.new(_TEST_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def _override_gallabox_secret():
    base_settings = get_settings()
    overridden = base_settings.model_copy(update={"gallabox_webhook_secret": _TEST_WEBHOOK_SECRET})
    app.dependency_overrides[get_settings] = lambda: overridden
    yield
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _make_business_and_contact(phone: str) -> tuple[uuid.UUID, uuid.UUID]:
    async with async_session_factory() as db:
        business = Business(
            name=f"WA Test {uuid.uuid4()}",
            category=BusinessCategory.salon_spa_gym,
            tier=BusinessTier.starter,
        )
        db.add(business)
        await db.flush()

        contact = WhatsAppContact(business_id=business.id, phone_e164=phone, opt_in=True)
        db.add(contact)
        await db.commit()
        return business.id, contact.id


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(client: AsyncClient):
    payload = json.dumps({"event": "message.received"}).encode()
    resp = await client.post(
        "/api/v1/webhooks/whatsapp/gallabox",
        content=payload,
        headers={"x-gallabox-signature": "not-the-real-signature"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_missing_signature(client: AsyncClient):
    payload = json.dumps({"event": "message.received"}).encode()
    resp = await client.post("/api/v1/webhooks/whatsapp/gallabox", content=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_inbound_message_opens_service_window(client: AsyncClient):
    business_id, contact_id = await _make_business_and_contact("+919999999001")

    payload = {
        "event": "message.received",
        "businessId": str(business_id),
        "id": "gallabox-inbound-1",
        "whatsapp": {"from": "+919999999001", "text": "hi there"},
    }
    body = json.dumps(payload).encode()
    resp = await client.post(
        "/api/v1/webhooks/whatsapp/gallabox",
        content=body,
        headers={"x-gallabox-signature": _sign(body)},
    )
    assert resp.status_code == 200, resp.text

    async with async_session_factory() as db:
        contact = (
            await db.execute(select(WhatsAppContact).where(WhatsAppContact.id == contact_id))
        ).scalar_one()
        assert contact.last_inbound_at is not None
        assert (datetime.now(UTC) - contact.last_inbound_at).total_seconds() < 30


@pytest.mark.asyncio
async def test_delivery_status_update_reaches_campaign_message(client: AsyncClient):
    business_id, contact_id = await _make_business_and_contact("+919999999002")
    # Unique per test run -- the Postgres instance persists across separate
    # pytest invocations (no per-test reset), so a fixed literal ID here
    # would collide with a prior run's row and break scalar_one_or_none().
    provider_message_id = f"gallabox-out-{uuid.uuid4()}"

    async with async_session_factory() as db:
        campaign = Campaign(
            business_id=business_id, name="Test Campaign", template_name="tpl", category="utility"
        )
        db.add(campaign)
        await db.flush()
        message = CampaignMessage(
            campaign_id=campaign.id,
            contact_id=contact_id,
            status="sent",
            provider_message_id=provider_message_id,
        )
        db.add(message)
        await db.commit()
        message_id = message.id

    payload = {
        "event": "status",
        "id": provider_message_id,
        "status": "delivered",
        "category": "utility",
    }
    body = json.dumps(payload).encode()
    resp = await client.post(
        "/api/v1/webhooks/whatsapp/gallabox",
        content=body,
        headers={"x-gallabox-signature": _sign(body)},
    )
    assert resp.status_code == 200, resp.text

    async with async_session_factory() as db:
        message = (
            await db.execute(select(CampaignMessage).where(CampaignMessage.id == message_id))
        ).scalar_one()
        assert message.status == "delivered"
