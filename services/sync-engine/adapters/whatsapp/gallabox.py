"""
services/sync-engine/adapters/whatsapp/gallabox.py

Concrete implementation for Gallabox — chosen as primary BSP given existing
production experience from the SKYi Zoho+Gallabox integration. Provider-
specific field names (channelId, etc.) are contained entirely within this
file per the abstraction contract in base.py.

Untestable end-to-end without real GALLABOX_API_KEY/API_SECRET/
WEBHOOK_SECRET — send_message will fail against Gallabox's live API with
the placeholder .env credentials. Webhook signature verification and
service-window tracking are fully local logic and ARE covered by tests
(fixture-based, see tests/test_whatsapp_webhook.py).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.core import WhatsAppContact

from .base import (
    ConversationStatus,
    DeliveryStatus,
    InboundMessage,
    MessageCategory,
    OutboundMessage,
    SendResult,
    WhatsAppBSPAdapter,
)

# Seed rates — MUST be moved to a config table (not a code constant) before
# production use, per base.py's estimate_cost_inr docstring. Source: Meta's
# published India rate card as researched Jan-2026.
_SEED_RATES_INR = {
    MessageCategory.MARKETING: 0.8631,
    MessageCategory.UTILITY: 0.115,
    MessageCategory.AUTHENTICATION: 0.115,
    MessageCategory.SERVICE: 0.0,
}

_BASE_URL = "https://server.gallabox.com/devapi"
_SERVICE_WINDOW = timedelta(hours=24)


class GallaboxSendError(Exception):
    pass


class GallaboxWebhookError(Exception):
    pass


class GallaboxAdapter(WhatsAppBSPAdapter):
    """One instance per request — holds the request's own AsyncSession so
    get_conversation_status/parse_webhook can read/write our own
    WhatsAppContact rows instead of round-tripping to Gallabox (see
    factory.py for construction)."""

    provider_name = "gallabox"

    def __init__(self, api_key: str, api_secret: str, webhook_secret: str, db: AsyncSession):
        self._api_key = api_key
        self._api_secret = api_secret
        self._webhook_secret = webhook_secret
        self._db = db

    async def send_message(self, message: OutboundMessage) -> SendResult:
        payload = {
            "channelId": self._api_key,
            "recipient": {"phone": message.to_phone_e164},
            "whatsapp": {
                "type": "template",
                "template": {
                    "name": message.template_name,
                    "params": message.variables,
                },
            },
        }
        async with httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={"apiKey": self._api_key, "apiSecret": self._api_secret},
            timeout=10.0,
        ) as client:
            resp = await client.post("/messages/whatsapp", json=payload)

        if resp.status_code >= 300:
            # Typed exception so calling code (billing) can roll back the
            # pre-flight credit debit if the send actually fails.
            raise GallaboxSendError(f"Gallabox send failed: {resp.status_code} {resp.text}")

        data = resp.json()
        return SendResult(
            provider_message_id=data.get("id", ""),
            status=DeliveryStatus.SENT,
            category=message.category,
            estimated_cost_inr=self.estimate_cost_inr(message.category),
            sent_at=datetime.now(UTC),
        )

    def _verify_signature(self, raw_body: bytes, headers: dict) -> None:
        signature = headers.get("x-gallabox-signature") or headers.get("X-Gallabox-Signature", "")
        if not signature or not self._webhook_secret:
            raise GallaboxWebhookError("missing signature or webhook secret not configured")
        expected = hmac.new(self._webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise GallaboxWebhookError("signature mismatch")

    async def parse_webhook(self, raw_body: bytes, headers: dict) -> InboundMessage | SendResult:
        self._verify_signature(raw_body, headers)
        payload = json.loads(raw_body)
        event_type = payload.get("event") or payload.get("type")

        if event_type in ("message.received", "inbound"):
            wa = payload.get("whatsapp", {})
            business_id = uuid.UUID(payload["businessId"])
            from_phone = wa["from"]
            received_at = datetime.now(UTC)

            contact = (
                await self._db.execute(
                    select(WhatsAppContact).where(
                        WhatsAppContact.business_id == business_id,
                        WhatsAppContact.phone_e164 == from_phone,
                    )
                )
            ).scalar_one_or_none()
            if contact is not None:
                contact.last_inbound_at = received_at
            # else: inbound from a number we have no contact record for —
            # campaign targeting requires an explicit contact list per
            # 06_MODULES/CUSTOMER.md, so we don't silently create one here.

            return InboundMessage(
                business_id=str(business_id),
                from_phone_e164=from_phone,
                text=wa.get("text"),
                provider_message_id=payload.get("id", ""),
                received_at=received_at,
                opens_service_window=True,
            )

        # Delivery-status update for a message we sent.
        status_map = {
            "sent": DeliveryStatus.SENT,
            "delivered": DeliveryStatus.DELIVERED,
            "read": DeliveryStatus.READ,
            "failed": DeliveryStatus.FAILED,
        }
        return SendResult(
            provider_message_id=payload.get("id", ""),
            status=status_map.get(payload.get("status", ""), DeliveryStatus.QUEUED),
            category=MessageCategory(payload.get("category", MessageCategory.UTILITY.value)),
            estimated_cost_inr=None,
            sent_at=datetime.now(UTC),
        )

    async def get_conversation_status(self, business_id: str, phone_e164: str) -> ConversationStatus:
        contact = (
            await self._db.execute(
                select(WhatsAppContact).where(
                    WhatsAppContact.business_id == uuid.UUID(business_id),
                    WhatsAppContact.phone_e164 == phone_e164,
                )
            )
        ).scalar_one_or_none()

        if contact is None or contact.last_inbound_at is None:
            return ConversationStatus(
                business_id=business_id,
                counterpart_phone_e164=phone_e164,
                service_window_open=False,
                service_window_expires_at=None,
            )

        expires_at = contact.last_inbound_at + _SERVICE_WINDOW
        return ConversationStatus(
            business_id=business_id,
            counterpart_phone_e164=phone_e164,
            service_window_open=expires_at > datetime.now(UTC),
            service_window_expires_at=expires_at,
        )

    def estimate_cost_inr(self, category: MessageCategory, recipient_country: str = "IN") -> float:
        # TODO: replace _SEED_RATES_INR lookup with a real rates table read
        # once the config-table pattern is built (see module docstring).
        return _SEED_RATES_INR.get(category, 0.0)
