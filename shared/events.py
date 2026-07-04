"""
shared/events.py

Redis pub/sub publish side for internal events (not external webhooks),
per docs/PRESENCE/03_ARCHITECTURE/EVENT_ARCHITECTURE.md. Reuses the
existing Redis instance already running for Celery — no Kafka, not until
real volume justifies it (that doc's own Phase 3+ decision point).

Only publish_event() is implemented here — no subscriber exists in this
pass. A dedicated consumer (e.g. a future win-back-workflow service
reacting to business.churned) is the natural place to add one; there is
no caller for a generic subscribe() yet, so it isn't built speculatively.
Notification delivery in this pass (services/notifications/notifier.py)
calls this at the point the domain event happens, not via a listener.
"""
from __future__ import annotations

import json
from enum import Enum

from redis.asyncio import Redis


class EventType(str, Enum):
    PLATFORM_CONNECTION_DEGRADED = "platform.connection.degraded"
    REVIEW_RECEIVED = "review.received"
    WHATSAPP_MESSAGE_DELIVERED = "whatsapp.message.delivered"
    WHATSAPP_MESSAGE_FAILED = "whatsapp.message.failed"
    BUSINESS_CHURNED = "business.churned"


_CHANNEL_PREFIX = "presence_events"


def _channel(event_type: EventType) -> str:
    return f"{_CHANNEL_PREFIX}:{event_type.value}"


async def publish_event(redis_url: str, event_type: EventType, payload: dict) -> None:
    client = Redis.from_url(redis_url)
    try:
        await client.publish(_channel(event_type), json.dumps(payload, default=str))
    finally:
        await client.aclose()
