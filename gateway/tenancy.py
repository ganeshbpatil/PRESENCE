"""
gateway/tenancy.py

Shared row-level tenant-access check, reused by every router scoped to a
single business (businesses/reviews/whatsapp/attribution/social/billing).
See the build plan's flagged note: this is row-level FK scoping
(business_id/agency_id), not DATABASE_ARCHITECTURE.md's schema-per-agency
plan — that doc and the already-merged schema disagree, and retrofitting
schema-per-tenant is a separate project, not something to bolt on here.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.core import Business, User


async def get_business_or_404(business_id: uuid.UUID, db: AsyncSession) -> Business:
    business = (
        await db.execute(select(Business).where(Business.id == business_id))
    ).scalar_one_or_none()
    if business is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    return business


def assert_can_access_business(user: User, business: Business) -> None:
    if user.business_id == business.id:
        return
    if user.agency_id is not None and user.agency_id == business.agency_id:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized for this business")


async def require_business_access(
    business_id: uuid.UUID, user: User, db: AsyncSession
) -> Business:
    business = await get_business_or_404(business_id, db)
    assert_can_access_business(user, business)
    return business
