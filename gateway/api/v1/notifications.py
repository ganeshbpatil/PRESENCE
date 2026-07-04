"""
gateway/api/v1/notifications.py

In-app notification inbox — in-app + email only for v1 per
06_MODULES/NOTIFICATIONS.md. Only "in_app" channel rows are user-facing
here; "email" channel rows exist purely as a delivery-audit record (see
services/notifications/notifier.py).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db import get_db
from gateway.security import get_current_user
from shared.models.core import NotificationEntry, User

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    payload: dict | None
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[NotificationEntry]:
    query = select(NotificationEntry).where(NotificationEntry.channel == "in_app")
    if user.business_id is not None:
        query = query.where(NotificationEntry.business_id == user.business_id)
    elif user.agency_id is not None:
        query = query.where(NotificationEntry.agency_id == user.agency_id)
    else:
        return []
    query = query.order_by(NotificationEntry.created_at.desc())
    return list((await db.execute(query)).scalars().all())


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationEntry:
    notification = (
        await db.execute(
            select(NotificationEntry).where(NotificationEntry.id == notification_id)
        )
    ).scalar_one_or_none()
    if notification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")

    owned = (user.business_id is not None and notification.business_id == user.business_id) or (
        user.agency_id is not None and notification.agency_id == user.agency_id
    )
    if not owned:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized for this notification")

    notification.read_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(notification)
    return notification
