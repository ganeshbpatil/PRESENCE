"""
gateway/api/v1/oauth.py

OAuth authorize/callback scaffold for GBP/Meta platform connections,
replacing the current raw-token-in-a-form flow (businesses.py's
ConnectionCreate.access_token) once real credentials exist. Confirmed
sequencing: build everything verifiable now (CSRF-state creation,
single-use/expiry validation, config-status reporting), leave the actual
authorize-URL construction and token exchange as an explicit 501 -- do
not hardcode a guessed Google/Meta OAuth endpoint or scope list without a
way to verify it against a real registered app (see gateway/config.py's
gbp_client_id/meta_app_id, both empty until Ganesh registers one).
"""
from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.config import Settings, get_settings
from gateway.db import get_db
from gateway.security import get_current_user
from gateway.tenancy import require_business_write_access
from shared.models.core import OAuthState, PlatformName, User

router = APIRouter(tags=["oauth"])

# Short-lived, single-use (used_at) CSRF nonce -- generous enough for a
# human to complete a consent screen, tight enough that a leaked/logged
# state param is useless soon after.
_STATE_TTL = timedelta(minutes=10)


class OAuthStatusResponse(BaseModel):
    gbp_configured: bool
    meta_configured: bool


@router.get("/oauth/status", response_model=OAuthStatusResponse)
async def oauth_status(
    settings: Settings = Depends(get_settings),
    _user: User = Depends(get_current_user),
) -> OAuthStatusResponse:
    return OAuthStatusResponse(
        gbp_configured=bool(settings.gbp_client_id and settings.gbp_client_secret),
        meta_configured=bool(settings.meta_app_id and settings.meta_app_secret),
    )


@router.post("/businesses/{business_id}/connections/{platform}/oauth/start")
async def start_oauth(
    business_id: uuid.UUID,
    platform: PlatformName,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    await require_business_write_access(business_id, user, db)

    if platform == PlatformName.whatsapp:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "WhatsApp uses API-key auth (Gallabox), not OAuth"
        )
    if platform == PlatformName.gbp and not (
        settings.gbp_client_id and settings.gbp_client_secret
    ):
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "GBP OAuth is not configured yet")
    if platform == PlatformName.meta and not (
        settings.meta_app_id and settings.meta_app_secret
    ):
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Meta OAuth is not configured yet")

    # The CSRF-state machinery is real and persisted even though the
    # redirect itself isn't built yet -- proves the part of this flow
    # that doesn't depend on knowing the provider's real endpoint shape.
    oauth_state = OAuthState(
        business_id=business_id,
        platform=platform,
        state=secrets.token_urlsafe(32),
        expires_at=datetime.now(UTC) + _STATE_TTL,
    )
    db.add(oauth_state)
    await db.commit()

    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        f"{platform.value} authorize-URL construction not implemented yet -- "
        "needs a verified endpoint/scope list against a real registered app",
    )


@router.get("/businesses/{business_id}/connections/{platform}/oauth/callback")
async def oauth_callback(
    business_id: uuid.UUID,
    platform: PlatformName,
    state: str,
    code: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # No get_current_user -- this is a browser redirect from the provider,
    # not an authenticated API call. The state param IS the security
    # boundary: unknown/reused/expired/mismatched all reject before code
    # (unused for now, see module docstring) ever matters.
    del code
    oauth_state = (
        await db.execute(select(OAuthState).where(OAuthState.state == state))
    ).scalar_one_or_none()

    if oauth_state is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown or invalid state")
    if oauth_state.used_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "State already used")
    if oauth_state.expires_at < datetime.now(UTC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "State expired")
    if oauth_state.business_id != business_id or oauth_state.platform != platform:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "State does not match business/platform")

    oauth_state.used_at = datetime.now(UTC)
    await db.commit()

    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        f"{platform.value} token exchange not implemented yet",
    )
