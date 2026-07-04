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

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db import get_db
from gateway.security import assert_valid_invite_code, get_current_user
from gateway.tenancy import require_business_access, require_business_write_access
from gateway.vault import get_vault_client
from shared.models.core import (
    Business,
    BusinessCategory,
    BusinessTier,
    PlatformConnection,
    PlatformName,
    SyncStatus,
    User,
)
from shared.secrets.vault_client import VaultClient, VaultError

router = APIRouter(prefix="/businesses", tags=["businesses"])


class BusinessCreate(BaseModel):
    name: str
    category: BusinessCategory
    tier: BusinessTier
    agency_id: uuid.UUID | None = None
    pincode: str | None = None
    area: str | None = None
    # Required when settings.signup_invite_code is set (production) --
    # see gateway/security.py's assert_valid_invite_code.
    invite_code: str | None = None


class BusinessUpdate(BaseModel):
    # All optional -- PATCH semantics, only set fields are touched.
    # Deliberately no agency_id here: reassigning a business between
    # agencies has billing/attribution-history implications that deserve
    # their own explicit, audited operation later, not a silent field on a
    # generic edit form.
    name: str | None = None
    category: BusinessCategory | None = None
    tier: BusinessTier | None = None
    pincode: str | None = None
    area: str | None = None
    subscription_status: str | None = None


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
    # Raw token, write-only -- never echoed back (ConnectionResponse omits
    # it) and never stored in Postgres. Immediately written to Vault and
    # replaced with a KV path reference before the row is persisted, per
    # SECURITY_ARCHITECTURE.md's Secrets Management section.
    access_token: str | None = None


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
    # unauthenticated -- gated instead by a shared invite code (see
    # gateway/security.py's assert_valid_invite_code) so the public API
    # can't be used to spin up arbitrary business shells in production.
    assert_valid_invite_code(body.invite_code)
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


@router.patch("/{business_id}", response_model=BusinessResponse)
async def update_business(
    business_id: uuid.UUID,
    body: BusinessUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Business:
    business = await require_business_write_access(business_id, user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(business, field, value)
    await db.commit()
    await db.refresh(business)
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
    vault: VaultClient = Depends(get_vault_client),
) -> PlatformConnection:
    await require_business_write_access(business_id, user, db)

    access_token_ref = None
    if body.access_token:
        access_token_ref = VaultClient.ref_for(business_id, body.platform.value)
        try:
            await vault.store(access_token_ref, body.access_token)
        except VaultError as exc:
            # Degrade, don't silently persist a connection that looks
            # healthy but has no retrievable token (CLAUDE.md principle #1
            # applied to vault-dependence) -- fail the request instead.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not store platform credential in vault",
            ) from exc

    connection = PlatformConnection(
        business_id=business_id,
        platform=body.platform,
        provider=body.provider,
        external_id=body.external_id,
        access_token_ref=access_token_ref,
        sync_status=SyncStatus.healthy,
        last_synced_at=datetime.now(UTC) if access_token_ref else None,
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
