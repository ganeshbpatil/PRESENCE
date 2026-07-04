"""
gateway/api/v1/social.py

Social module — narrow scope per 06_MODULES/SOCIAL.md: schedule posts,
list them. Actual publishing happens on a Celery-beat schedule (see
gateway/tasks/sync.py), never synchronously from this endpoint.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db import get_db
from gateway.security import get_current_user
from gateway.tenancy import require_business_access, require_business_write_access
from shared.models.core import ScheduledPost, User

router = APIRouter(tags=["social"])


class ScheduledPostCreate(BaseModel):
    platform: str  # "meta" | "instagram"
    content: str
    media_url: str | None = None
    scheduled_at: datetime


class ScheduledPostResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    platform: str
    content: str
    media_url: str | None
    scheduled_at: datetime
    status: str
    posted_at: datetime | None

    model_config = {"from_attributes": True}


@router.post(
    "/businesses/{business_id}/social/posts",
    response_model=ScheduledPostResponse,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_post(
    business_id: uuid.UUID,
    body: ScheduledPostCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduledPost:
    await require_business_write_access(business_id, user, db)
    post = ScheduledPost(
        business_id=business_id,
        platform=body.platform,
        content=body.content,
        media_url=body.media_url,
        scheduled_at=body.scheduled_at,
        status="pending",
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


@router.get("/businesses/{business_id}/social/posts", response_model=list[ScheduledPostResponse])
async def list_posts(
    business_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ScheduledPost]:
    await require_business_access(business_id, user, db)
    result = await db.execute(
        select(ScheduledPost).where(ScheduledPost.business_id == business_id)
    )
    return list(result.scalars().all())
