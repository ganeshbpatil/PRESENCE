"""
gateway/api/v1/businesses.py

Business = the tenant-scoped root entity (06_MODULES/BUSINESS.md). Also
owns the platform-connection endpoints — /connections here are connection
*records* (GBP/Meta/WhatsApp), not the live OAuth handshake itself (that
needs real client IDs/secrets and is out of scope for this pass).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db import get_db
from gateway.security import get_current_user
from gateway.tenancy import require_business_access
from shared.models.core import (
    Business,
    BusinessCategory,
    BusinessTier,
    PlatformConnection,
    PlatformName,
    SyncStatus,
    User,
)

router = APIRouter(prefix="/businesses", tags=["businesses"])


class BusinessCreate(BaseModel):
    name: str
    category: BusinessCategory
    tier: BusinessTier
    agency_id: uuid.UUID | None = None
    pincode: str | None = None
    area: str | None = None


class BusinessResponse(BaseModel):
    id: uuid.UUID
    name: str
    category: BusinessCategory
    tier: BusinessTier
    agency_id: uuid.UUID | None
    subscription_status: str | None
    pincode: str | None
    area: str | None

    model_config = {"from_attributes": True}


class ConnectionCreate(BaseModel):
    platform: PlatformName
    provider: str | None = None
    external_id: str | None = None
    access_token_ref: str | None = None


class ConnectionResponse(BaseModel):
    id: uuid.UUID
    platform: PlatformName
    provider: str | None
    external_id: str | None
    sync_status: SyncStatus
    last_synced_at: datetime | None

    model_config = {"from_attributes": True}


@router.post("", response_model=BusinessResponse, status_code=status.HTTP_201_CREATED)
async def create_business(body: BusinessCreate, db: AsyncSession = Depends(get_db)) -> Business:
    # Signup happens before a user exists (a business must exist first for
    # smb_owner signup to reference), so this endpoint is intentionally
    # unauthenticated — tightening this (e.g. an invite-code flow) is a
    # follow-up once onboarding is designed, not silently skipped here.
    business = Business(
        name=body.name,
        category=body.category,
        tier=body.tier,
        agency_id=body.agency_id,
        pincode=body.pincode,
        area=body.area,
    )
    db.add(business)
    await db.commit()
    await db.refresh(business)
    return business


@router.get("/{business_id}", response_model=BusinessResponse)
async def get_business(
    business_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Business:
    business = await require_business_access(business_id, user, db)
    return business


@router.post(
    "/{business_id}/connections",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_connection(
    business_id: uuid.UUID,
    body: ConnectionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlatformConnection:
    await require_business_access(business_id, user, db)

    connection = PlatformConnection(
        business_id=business_id,
        platform=body.platform,
        provider=body.provider,
        external_id=body.external_id,
        access_token_ref=body.access_token_ref,
        sync_status=SyncStatus.healthy,
        last_synced_at=datetime.now(UTC) if body.access_token_ref else None,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


@router.get("/{business_id}/connections/health", response_model=list[ConnectionResponse])
async def connections_health(
    business_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PlatformConnection]:
    await require_business_access(business_id, user, db)

    result = await db.execute(
        select(PlatformConnection).where(PlatformConnection.business_id == business_id)
    )
    return list(result.scalars().all())
