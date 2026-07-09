"""
gateway/api/v1/oauth.py

OAuth authorize/callback flow for GBP/Meta platform connections, replacing
the raw-token-in-a-form flow (businesses.py's ConnectionCreate.access_token)
for those two platforms. WhatsApp stays API-key auth via Gallabox.

The callback route is a FIXED path per platform (/oauth/callback/{platform}),
not templated with business_id -- neither Google nor Meta support wildcard
redirect URIs, the registered URI must match exactly what's configured in
each provider's console. Tenant context rides in the `state` param instead,
resolved from the OAuthState row /start created (see gateway/config.py's
gbp_redirect_uri/meta_redirect_uri).

Scopes/endpoints below are each provider's standard OAuth surface for the
data this app already reads/writes (Meta Page insights + posts via
services/sync-engine/adapters/social/meta.py; GBP's
business.manage scope covers both the Performance and Local Posts APIs
that gbp.py will eventually call). Not verified against Ganesh's actual
registered apps' App Review / consent-screen state -- confirm
pages_show_list/pages_read_engagement/pages_manage_posts are approved
scopes for the Meta app before relying on this in production for
non-admin/tester accounts.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.config import Settings, get_settings
from gateway.db import get_db
from gateway.security import get_current_user
from gateway.tenancy import require_business_write_access
from gateway.vault import get_vault_client
from shared.models.core import OAuthState, PlatformConnection, PlatformName, SyncStatus, User
from shared.secrets.vault_client import VaultClient, VaultError

router = APIRouter(tags=["oauth"])

# Short-lived, single-use (used_at) CSRF nonce -- generous enough for a
# human to complete a consent screen, tight enough that a leaked/logged
# state param is useless soon after.
_STATE_TTL = timedelta(minutes=10)

_GBP_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GBP_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GBP_SCOPE = "https://www.googleapis.com/auth/business.manage"

_META_AUTHORIZE_URL = "https://www.facebook.com/v19.0/dialog/oauth"
_META_TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
_META_SCOPE = "pages_show_list,pages_read_engagement,pages_manage_posts"


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
        settings.gbp_client_id and settings.gbp_client_secret and settings.gbp_redirect_uri
    ):
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "GBP OAuth is not configured yet")
    if platform == PlatformName.meta and not (
        settings.meta_app_id and settings.meta_app_secret and settings.meta_redirect_uri
    ):
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Meta OAuth is not configured yet")

    state_value = secrets.token_urlsafe(32)
    oauth_state = OAuthState(
        business_id=business_id,
        platform=platform,
        state=state_value,
        expires_at=datetime.now(UTC) + _STATE_TTL,
    )
    db.add(oauth_state)
    await db.commit()

    if platform == PlatformName.gbp:
        params = {
            "client_id": settings.gbp_client_id,
            "redirect_uri": settings.gbp_redirect_uri,
            "response_type": "code",
            "scope": _GBP_SCOPE,
            # offline+consent is required every time to guarantee Google
            # actually returns a refresh_token -- it's otherwise only
            # issued on a user's very first consent for this app.
            "access_type": "offline",
            "prompt": "consent",
            "state": state_value,
        }
        authorize_url = f"{_GBP_AUTHORIZE_URL}?{urlencode(params)}"
    else:
        params = {
            "client_id": settings.meta_app_id,
            "redirect_uri": settings.meta_redirect_uri,
            "state": state_value,
            "scope": _META_SCOPE,
        }
        authorize_url = f"{_META_AUTHORIZE_URL}?{urlencode(params)}"

    return {"authorize_url": authorize_url}


@router.get("/oauth/callback/{platform}")
async def oauth_callback(
    platform: PlatformName,
    state: str,
    code: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    vault: VaultClient = Depends(get_vault_client),
) -> dict:
    # No get_current_user -- this is a browser redirect from the provider,
    # not an authenticated API call. The state param IS the security
    # boundary: unknown/reused/expired/platform-mismatched all reject
    # before code ever matters.
    oauth_state = (
        await db.execute(select(OAuthState).where(OAuthState.state == state))
    ).scalar_one_or_none()

    if oauth_state is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown or invalid state")
    if oauth_state.used_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "State already used")
    if oauth_state.expires_at < datetime.now(UTC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "State expired")
    if oauth_state.platform != platform:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "State does not match platform")

    oauth_state.used_at = datetime.now(UTC)
    await db.commit()

    if error is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"{platform.value} authorization was denied: {error}"
        )
    if code is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing authorization code")

    business_id = oauth_state.business_id

    existing = (
        await db.execute(
            select(PlatformConnection).where(
                PlatformConnection.business_id == business_id,
                PlatformConnection.platform == platform,
            )
        )
    ).scalar_one_or_none()

    if platform == PlatformName.gbp:
        token_data = await _exchange_gbp_code(settings, code)
        refresh_token = token_data.get("refresh_token")
        raw_scope = token_data.get("scope")
        scopes = raw_scope.split() if raw_scope else None
    elif platform == PlatformName.meta:
        token_data = await _exchange_meta_code(settings, code)
        # Meta has no refresh_token concept -- the long-lived token (~60
        # days) is the whole story, re-auth is required after it expires.
        refresh_token = None
        scopes = None
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "WhatsApp uses API-key auth, not OAuth"
        )

    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in")
    token_expires_at = (
        datetime.now(UTC) + timedelta(seconds=int(expires_in)) if expires_in else None
    )

    ref = VaultClient.ref_for(business_id, platform.value)
    vault_fields = {"access_token": access_token}
    if refresh_token:
        vault_fields["refresh_token"] = refresh_token
    elif existing is not None and existing.refresh_token_ref is not None:
        # Vault KV v2's write REPLACES the whole secret (see
        # VaultClient.store's docstring) -- if this exchange didn't return
        # a fresh refresh_token (e.g. a provider skips it on some
        # reconnects), pull the one already stored forward so this write
        # doesn't silently wipe it out from under the existing connection.
        try:
            vault_fields["refresh_token"] = await vault.resolve(ref, key="refresh_token")
        except VaultError:
            pass  # nothing to preserve -- fall through, store() just won't set it
    try:
        await vault.store(ref, **vault_fields)
    except VaultError as exc:
        # Degrade, don't silently persist a connection that looks healthy
        # but has no retrievable token (CLAUDE.md principle #1 applied to
        # vault-dependence) -- fail the request instead.
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Could not store platform credential in vault"
        ) from exc

    if existing is not None:
        existing.access_token_ref = ref
        existing.refresh_token_ref = ref if refresh_token else existing.refresh_token_ref
        existing.token_expires_at = token_expires_at
        existing.scopes = scopes
        existing.sync_status = SyncStatus.healthy
        existing.last_synced_at = datetime.now(UTC)
    else:
        db.add(
            PlatformConnection(
                business_id=business_id,
                platform=platform,
                access_token_ref=ref,
                refresh_token_ref=ref if refresh_token else None,
                token_expires_at=token_expires_at,
                scopes=scopes,
                sync_status=SyncStatus.healthy,
                last_synced_at=datetime.now(UTC),
            )
        )
    await db.commit()

    return {"connected": True, "platform": platform.value}


async def _exchange_gbp_code(settings: Settings, code: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _GBP_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.gbp_client_id,
                "client_secret": settings.gbp_client_secret,
                "redirect_uri": settings.gbp_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code >= 300:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"GBP token exchange failed: {resp.text}"
        )
    return resp.json()


async def _exchange_meta_code(settings: Settings, code: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            _META_TOKEN_URL,
            params={
                "client_id": settings.meta_app_id,
                "redirect_uri": settings.meta_redirect_uri,
                "client_secret": settings.meta_app_secret,
                "code": code,
            },
        )
    if resp.status_code >= 300:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Meta token exchange failed: {resp.text}"
        )
    short_lived = resp.json()

    # The code exchange above returns a short-lived (~1-2h) user token.
    # Trade it for a long-lived one (~60 days) up front so a connection
    # doesn't silently die a couple hours after being created.
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            _META_TOKEN_URL,
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "fb_exchange_token": short_lived["access_token"],
            },
        )
    if resp.status_code >= 300:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Meta long-lived token exchange failed: {resp.text}"
        )
    return resp.json()
