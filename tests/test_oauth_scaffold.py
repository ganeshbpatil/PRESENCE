"""
OAuth scaffold (gateway/api/v1/oauth.py). The CSRF-state machinery
(creation, single-use, expiry, mismatch rejection) is real and tested
here; the actual provider token exchange is deliberately unimplemented
(501) -- see the module docstring for why.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from gateway.config import get_settings
from gateway.db import async_session_factory
from gateway.main import app
from shared.models.core import BusinessCategory, BusinessTier, OAuthState, PlatformName


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def _configure_gbp_and_meta():
    base_settings = get_settings()
    overridden = base_settings.model_copy(
        update={
            "gbp_client_id": "test-gbp-client",
            "gbp_client_secret": "test-gbp-secret",
            "meta_app_id": "test-meta-app",
            "meta_app_secret": "test-meta-secret",
        }
    )
    app.dependency_overrides[get_settings] = lambda: overridden
    yield
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture
def _unconfigure_gbp_and_meta():
    base_settings = get_settings()
    overridden = base_settings.model_copy(
        update={
            "gbp_client_id": "",
            "gbp_client_secret": "",
            "meta_app_id": "",
            "meta_app_secret": "",
        }
    )
    app.dependency_overrides[get_settings] = lambda: overridden
    yield
    app.dependency_overrides.pop(get_settings, None)


async def _signup_owner(client: AsyncClient) -> tuple[str, dict]:
    biz = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"OAuth Test {uuid.uuid4()}",
            "category": BusinessCategory.salon_spa_gym.value,
            "tier": BusinessTier.starter.value,
            "invite_code": get_settings().signup_invite_code,
        },
    )
    business_id = biz.json()["id"]
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"owner-{uuid.uuid4()}@example.com",
            "password": "correct-horse-battery",
            "role": "smb_owner",
            "business_id": business_id,
        },
    )
    token = signup.json()["access_token"]
    return business_id, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_oauth_status_reports_configured_platforms(client, _configure_gbp_and_meta):
    _business_id, headers = await _signup_owner(client)
    resp = await client.get("/api/v1/oauth/status", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"gbp_configured": True, "meta_configured": True}


@pytest.mark.asyncio
async def test_oauth_status_reports_unconfigured(client, _unconfigure_gbp_and_meta):
    _business_id, headers = await _signup_owner(client)
    resp = await client.get("/api/v1/oauth/status", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"gbp_configured": False, "meta_configured": False}


@pytest.mark.asyncio
async def test_start_oauth_returns_501_when_unconfigured(client, _unconfigure_gbp_and_meta):
    business_id, headers = await _signup_owner(client)
    resp = await client.post(
        f"/api/v1/businesses/{business_id}/connections/gbp/oauth/start", headers=headers
    )
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_start_oauth_creates_state_row_then_501s_when_configured(
    client, _configure_gbp_and_meta
):
    business_id, headers = await _signup_owner(client)
    resp = await client.post(
        f"/api/v1/businesses/{business_id}/connections/gbp/oauth/start", headers=headers
    )
    assert resp.status_code == 501

    async with async_session_factory() as db:
        rows = list(
            (
                await db.execute(
                    select(OAuthState).where(OAuthState.business_id == uuid.UUID(business_id))
                )
            ).scalars()
        )
        assert len(rows) == 1
        assert rows[0].platform == PlatformName.gbp
        assert rows[0].used_at is None


@pytest.mark.asyncio
async def test_start_oauth_rejects_whatsapp_platform(client, _configure_gbp_and_meta):
    business_id, headers = await _signup_owner(client)
    resp = await client.post(
        f"/api/v1/businesses/{business_id}/connections/whatsapp/oauth/start", headers=headers
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_start_oauth_requires_write_access(client, _configure_gbp_and_meta):
    business_id, _headers = await _signup_owner(client)
    _other_business_id, other_headers = await _signup_owner(client)
    resp = await client.post(
        f"/api/v1/businesses/{business_id}/connections/gbp/oauth/start", headers=other_headers
    )
    assert resp.status_code == 403


async def _make_state(
    business_id: uuid.UUID,
    platform: PlatformName = PlatformName.gbp,
    *,
    expires_in: timedelta = timedelta(minutes=10),
    used: bool = False,
) -> str:
    async with async_session_factory() as db:
        state_value = f"test-state-{uuid.uuid4()}"
        oauth_state = OAuthState(
            business_id=business_id,
            platform=platform,
            state=state_value,
            expires_at=datetime.now(UTC) + expires_in,
            used_at=datetime.now(UTC) if used else None,
        )
        db.add(oauth_state)
        await db.commit()
        return state_value


@pytest.mark.asyncio
async def test_callback_accepts_valid_state_then_501s(client):
    business_id, headers = await _signup_owner(client)
    state = await _make_state(uuid.UUID(business_id))

    resp = await client.get(
        f"/api/v1/businesses/{business_id}/connections/gbp/oauth/callback",
        params={"state": state, "code": "fake-code"},
        headers=headers,
    )
    assert resp.status_code == 501

    async with async_session_factory() as db:
        row = (
            await db.execute(select(OAuthState).where(OAuthState.state == state))
        ).scalar_one()
        assert row.used_at is not None


@pytest.mark.asyncio
async def test_callback_rejects_unknown_state(client):
    business_id, headers = await _signup_owner(client)
    resp = await client.get(
        f"/api/v1/businesses/{business_id}/connections/gbp/oauth/callback",
        params={"state": "never-issued"},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_callback_rejects_already_used_state(client):
    business_id, headers = await _signup_owner(client)
    state = await _make_state(uuid.UUID(business_id), used=True)
    resp = await client.get(
        f"/api/v1/businesses/{business_id}/connections/gbp/oauth/callback",
        params={"state": state},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_callback_rejects_expired_state(client):
    business_id, headers = await _signup_owner(client)
    state = await _make_state(uuid.UUID(business_id), expires_in=timedelta(minutes=-1))
    resp = await client.get(
        f"/api/v1/businesses/{business_id}/connections/gbp/oauth/callback",
        params={"state": state},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_callback_rejects_platform_mismatch(client):
    business_id, headers = await _signup_owner(client)
    state = await _make_state(uuid.UUID(business_id), platform=PlatformName.meta)
    resp = await client.get(
        f"/api/v1/businesses/{business_id}/connections/gbp/oauth/callback",
        params={"state": state},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_callback_rejects_business_mismatch(client):
    business_id, headers = await _signup_owner(client)
    other_business_id, _other_headers = await _signup_owner(client)
    state = await _make_state(uuid.UUID(other_business_id))

    resp = await client.get(
        f"/api/v1/businesses/{business_id}/connections/gbp/oauth/callback",
        params={"state": state},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_gbp_adapter_raises_not_implemented():
    import importlib

    gbp_mod = importlib.import_module("services.sync-engine.adapters.social.gbp")
    adapter = gbp_mod.GBPAdapter(access_token="fake")
    with pytest.raises(gbp_mod.GBPAdapterError):
        await adapter.get_insights("locations/1", datetime.now(UTC), datetime.now(UTC))
    with pytest.raises(gbp_mod.GBPAdapterError):
        await adapter.create_post("locations/1", "hello", None)
