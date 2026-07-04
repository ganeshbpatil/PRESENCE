"""
services/sync-engine/adapters/whatsapp/base.py

THE CONTRACT. Every BSP adapter (Gallabox, Gupshup, Interakt, ...) implements
this interface. Calling code (billing, campaigns, review-request triggers)
depends ONLY on this abstract interface, never on a concrete adapter class.

Why this exists (see CLAUDE.md principle #2, and the sourced risk data in
the diligence memo): Meta changed WhatsApp billing from per-conversation to
per-message in July 2025, and raised India rates again in Jan 2026. BSPs
pass these changes through, sometimes with their own pricing/API changes on
top. A BSP swap must be a config change + new adapter file, never a rewrite
of campaign/billing logic.

Adding a new BSP: implement this interface, add a fixture-based test using
recorded sample webhook/API responses (see tests/unit/adapters/), register
it in the provider factory, done. Do not leak provider-specific fields
(e.g. Gallabox's channelId) into any code outside this adapter's own file.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MessageCategory(str, Enum):
    """
    Mirrors Meta's own billing categories — kept identical to Meta's
    taxonomy (not the BSP's) because pricing/compliance logic is written
    against THIS enum, not against whatever the BSP happens to call it.
    """
    MARKETING = "marketing"
    UTILITY = "utility"
    AUTHENTICATION = "authentication"
    SERVICE = "service"  # free, inside 24hr window


class DeliveryStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


@dataclass
class OutboundMessage:
    business_id: str
    to_phone_e164: str
    template_name: str
    category: MessageCategory
    variables: dict[str, str]
    campaign_ref: str | None = None


@dataclass
class SendResult:
    provider_message_id: str
    status: DeliveryStatus
    category: MessageCategory
    estimated_cost_inr: float | None  # for real-time credit-ledger debiting
    sent_at: datetime


@dataclass
class InboundMessage:
    """Normalized inbound webhook payload — provider-agnostic shape."""
    business_id: str
    from_phone_e164: str
    text: str | None
    provider_message_id: str
    received_at: datetime
    opens_service_window: bool = True  # inbound msg opens the free 24hr window


@dataclass
class ConversationStatus:
    business_id: str
    counterpart_phone_e164: str
    service_window_open: bool
    service_window_expires_at: datetime | None


class WhatsAppBSPAdapter(ABC):
    """Abstract base — one subclass per BSP. Never instantiate directly."""

    provider_name: str  # set by subclass, matches platform_connections.provider

    @abstractmethod
    async def send_message(self, message: OutboundMessage) -> SendResult:
        """Send a template message. Must classify category correctly —
        misclassification is the #1 cost mistake per sourced pricing research
        (marketing messages cost ~6-8x utility/authentication in India)."""
        ...

    @abstractmethod
    async def parse_webhook(self, raw_body: bytes, headers: dict) -> InboundMessage | SendResult:
        """Normalize a provider webhook into our internal shape. Must verify
        webhook signature using the provider's own secret — never trust an
        unverified payload, this is a public-facing endpoint (see
        docker-compose.yml rate-limit middleware on this route).

        Takes raw_body (bytes), not a pre-parsed dict: HMAC signature
        verification must run over the exact bytes the provider signed —
        re-serializing an already-parsed dict is not guaranteed to
        reproduce the same byte stream (key order, whitespace), which would
        make verification silently unreliable. Parse JSON internally, after
        verifying."""
        ...

    @abstractmethod
    async def get_conversation_status(self, business_id: str, phone_e164: str) -> ConversationStatus:
        """Check whether the free 24hr service window is open — calling
        code uses this to route to SERVICE (free) vs template (paid) sends
        wherever possible, per the cost-optimization patterns sourced in
        the diligence memo's WhatsApp pricing research."""
        ...

    @abstractmethod
    def estimate_cost_inr(self, category: MessageCategory, recipient_country: str = "IN") -> float:
        """Return Meta's current base rate for cost estimation BEFORE send,
        so the credit-ledger check can happen pre-flight, not post-hoc.
        Rates change periodically (twice in the last 12 months per sourced
        research) — this should read from a config/rates table, not a
        hardcoded constant, so an ops update doesn't require a code deploy."""
        ...
