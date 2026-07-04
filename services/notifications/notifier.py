"""
services/notifications/notifier.py

Single entry point for creating a notification: writes a NotificationEntry
row, publishes to the internal Redis event bus (shared/events.py) for any
future dedicated subscriber, and sends the email channel (off the event
loop thread) if a recipient is found.

Called directly from the code path where the domain event actually
happens (reviews.py on review creation, whatsapp.py on delivery-status
change) rather than via a persistent pub/sub listener — Celery's worker
model is task-based, not a long-running subscriber, so a real subscriber
would need its own supervisor process, out of scope here. publish_event()
still fires so the channel exists for whenever that consumer is built.
"""
from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.events import EventType, publish_event
from shared.models.core import NotificationEntry, User

from .email import send_email


async def _resolve_recipient_email(
    db: AsyncSession, business_id: uuid.UUID | None, agency_id: uuid.UUID | None
) -> str | None:
    if business_id is not None:
        user = (
            await db.execute(select(User).where(User.business_id == business_id))
        ).scalars().first()
    elif agency_id is not None:
        user = (
            await db.execute(select(User).where(User.agency_id == agency_id))
        ).scalars().first()
    else:
        user = None
    return user.email if user else None


async def notify(
    db: AsyncSession,
    event_type: EventType,
    payload: dict,
    *,
    redis_url: str,
    business_id: uuid.UUID | None = None,
    agency_id: uuid.UUID | None = None,
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_password: str = "",
    smtp_from_email: str = "",
) -> NotificationEntry:
    entry = NotificationEntry(
        business_id=business_id,
        agency_id=agency_id,
        event_type=event_type.value,
        payload=payload,
        channel="in_app",
    )
    db.add(entry)
    await db.flush()

    await publish_event(redis_url, event_type, payload)

    recipient = await _resolve_recipient_email(db, business_id, agency_id)
    if recipient:
        await asyncio.to_thread(
            send_email,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            from_email=smtp_from_email,
            to_email=recipient,
            subject=f"PRESENCE: {event_type.value}",
            body=str(payload),
        )
        db.add(
            NotificationEntry(
                business_id=business_id,
                agency_id=agency_id,
                event_type=event_type.value,
                payload=payload,
                channel="email",
            )
        )
        await db.flush()

    return entry
