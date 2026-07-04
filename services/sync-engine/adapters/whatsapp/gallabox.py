"""
services/sync-engine/adapters/whatsapp/gallabox.py

Concrete implementation for Gallabox — chosen as primary BSP given existing
production experience from the SKYi Zoho+Gallabox integration. Provider-
specific field names (channelId, etc.) are contained entirely within this
file per the abstraction contract in base.py.

TODO (first Claude Code session on this file):
- Wire real Gallabox API client (base URL, auth headers from GALLABOX_API_KEY/
  GALLABOX_API_SECRET in .env)
- Implement webhook signature verification using GALLABOX_WEBHOOK_SECRET
- Populate the rate table this reads from (see estimate_cost_inr) — use the
  sourced Jan 2026 India rates as the seed: marketing ~₹0.86/msg, utility/
  auth ~₹0.115/msg (verify against Meta's current published rate card before
  going live — these change periodically, don't trust this comment forever)
"""
from __future__ import annotations

from .base import (
    ConversationStatus,
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


class GallaboxAdapter(WhatsAppBSPAdapter):
    provider_name = "gallabox"

    def __init__(self, api_key: str, api_secret: str, webhook_secret: str):
        self._api_key = api_key
        self._api_secret = api_secret
        self._webhook_secret = webhook_secret
        # TODO: instantiate httpx.AsyncClient with base_url + auth headers

    async def send_message(self, message: OutboundMessage) -> SendResult:
        # TODO: POST to Gallabox's send-message endpoint with the mapped
        # template/category/variables payload. Raise a typed exception on
        # non-2xx so calling code (billing) can roll back the pre-flight
        # credit debit if the send actually fails.
        raise NotImplementedError("Wire Gallabox API client here")

    async def parse_webhook(self, raw_payload: dict, headers: dict):
        # TODO: verify signature (HMAC against self._webhook_secret) BEFORE
        # trusting raw_payload — this is an internet-facing endpoint.
        # Then branch on Gallabox's event type into either InboundMessage
        # (customer replied — opens service window) or SendResult (delivery
        # status update for a message we sent).
        raise NotImplementedError("Wire Gallabox webhook parsing here")

    async def get_conversation_status(self, business_id: str, phone_e164: str) -> ConversationStatus:
        # TODO: query our own platform_connections / last-inbound-message
        # record rather than calling Gallabox's API for this — we should be
        # tracking service-window state locally from inbound webhooks, not
        # round-tripping to the BSP on every send decision.
        raise NotImplementedError

    def estimate_cost_inr(self, category: MessageCategory, recipient_country: str = "IN") -> float:
        # TODO: replace _SEED_RATES_INR lookup with a real rates table read
        # (see module docstring) once the config-table pattern is built.
        return _SEED_RATES_INR.get(category, 0.0)
