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

from shared.models.core import Agency, Business, User, UserRole


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


def assert_can_write_business(user: User, business: Business) -> None:
    """Same tenancy check as assert_can_access_business, plus the RBAC rule
    from SECURITY_ARCHITECTURE.md that agency_viewer is read-only -- it was
    previously unenforced, letting a viewer perform any write an admin
    could (send WhatsApp campaigns, recharge credit, etc)."""
    assert_can_access_business(user, business)
    if user.role == UserRole.agency_viewer:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "agency_viewer role is read-only")


async def require_business_access(
    business_id: uuid.UUID, user: User, db: AsyncSession
) -> Business:
    business = await get_business_or_404(business_id, db)
    assert_can_access_business(user, business)
    return business


async def require_business_write_access(
    business_id: uuid.UUID, user: User, db: AsyncSession
) -> Business:
    business = await get_business_or_404(business_id, db)
    assert_can_write_business(user, business)
    return business


async def get_agency_or_404(agency_id: uuid.UUID, db: AsyncSession) -> Agency:
    agency = (
        await db.execute(select(Agency).where(Agency.id == agency_id))
    ).scalar_one_or_none()
    if agency is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agency not found")
    return agency


async def require_agency_access(
    agency_id: uuid.UUID, user: User, db: AsyncSession, *, write: bool = False
) -> Agency:
    """Promoted from agencies.py's former private _require_agency_access so
    it can be shared with the new agency write endpoints (create/edit,
    user management) added alongside this RBAC fix."""
    agency = await get_agency_or_404(agency_id, db)
    if user.agency_id != agency_id or user.role not in (
        UserRole.agency_admin,
        UserRole.agency_viewer,
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized for this agency")
    if write and user.role != UserRole.agency_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "agency_viewer role is read-only")
    return agency
