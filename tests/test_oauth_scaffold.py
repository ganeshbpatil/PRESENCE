"""
OAuth flow (gateway/api/v1/oauth.py). The CSRF-state machinery (creation,
single-use, expiry, platform mismatch) and the authorize-URL construction
are fully covered here. The real GBP/Meta token exchange is mocked at the
httpx layer (matching tests/test_vault_client.py's MockTransport
convention) since it talks to Google's/Meta's real endpoints; the
Vault-store step deliberately is NOT mocked and instead uses bogus AppRole
credentials to force a real failure against the test Vault container
(matching tests/test_platform_connections.py's precedent) -- a real
happy-path Vault write needs a live, unsealed Vault, out of scope here.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from gateway.config import get_settings
from gateway.db import async_session_factory
from gateway.main import app
from gateway.vault import get_vault_client
from shared.models.core import (
    BusinessCategory,
    BusinessTier,
    OAuthState,
    PlatformConnection,
    PlatformName,
)
from shared.secrets.vault_client import VaultClient


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
            "gbp_redirect_uri": "https://test.example.com/api/v1/oauth/callback/gbp",
            "meta_app_id": "test-meta-app",
            "meta_app_secret": "test-meta-secret",
            "meta_redirect_uri": "https://test.example.com/api/v1/oauth/callback/meta",
        }
    )
    app.dependency_overrides[get_settings] = lambda: overridden
    yield
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture
def _configure_without_redirect_uri():
    base_settings = get_settings()
    overridden = base_settings.model_copy(
        update={
            "gbp_client_id": "test-gbp-client",
            "gbp_client_secret": "test-gbp-secret",
            "gbp_redirect_uri": "",
            "meta_app_id": "test-meta-app",
            "meta_app_secret": "test-meta-secret",
            "meta_redirect_uri": "",
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


@pytest.fixture
def _bogus_vault():
    """Force a real AppRole login failure against the test Vault container
    (still reachable over the docker network, just not initialized/not
    authorized for these bogus IDs) instead of faking VaultClient -- same
    technique as test_platform_connections.py's vault-failure test."""

    def bogus_vault_client() -> VaultClient:
        base = get_settings()
        return VaultClient(
            addr=base.vault_addr,
            role_id="bogus-role-id",
            secret_id="bogus-secret-id",
            kv_mount=base.vault_kv_mount,
        )

    app.dependency_overrides[get_vault_client] = bogus_vault_client
    yield
    app.dependency_overrides.pop(get_vault_client, None)


@pytest.fixture
def _mock_provider_token_exchange(monkeypatch):
    """Routes only the GBP/Meta token-exchange calls through a
    MockTransport; calls that pass base_url= (i.e. VaultClient's, see
    shared/secrets/vault_client.py) are left untouched so vault fixtures
    still hit the real (test) Vault container."""
    real_async_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(
                200,
                json={
                    "access_token": "fake-gbp-access-token",
                    "refresh_token": "fake-gbp-refresh-token",
                    "expires_in": 3600,
                    "scope": "https://www.googleapis.com/auth/business.manage",
                    "token_type": "Bearer",
                },
            )
        if request.url.host == "graph.facebook.com":
            if b"fb_exchange_token" in request.url.query:
                return httpx.Response(
                    200,
                    json={
                        "access_token": "fake-meta-long-lived-token",
                        "expires_in": 5_184_000,
                    },
                )
            return httpx.Response(
                200,
                json={
                    "access_token": "fake-meta-short-lived-token",
                    "token_type": "bearer",
                    "expires_in": 5400,
                },
            )
        raise AssertionError(f"unexpected token-exchange request to {request.url}")

    def factory(*args, **kwargs):
        if "base_url" in kwargs:
            return real_async_client(*args, **kwargs)
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


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
            "invite_code": get_settings().signup_invite_code,
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
async def test_start_oauth_501s_when_redirect_uri_not_set(client, _configure_without_redirect_uri):
    business_id, headers = await _signup_owner(client)
    resp = await client.post(
        f"/api/v1/businesses/{business_id}/connections/gbp/oauth/start", headers=headers
    )
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_start_oauth_returns_real_authorize_url_for_gbp(client, _configure_gbp_and_meta):
    business_id, headers = await _signup_owner(client)
    resp = await client.post(
        f"/api/v1/businesses/{business_id}/connections/gbp/oauth/start", headers=headers
    )
    assert resp.status_code == 200, resp.text
    url = resp.json()["authorize_url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=test-gbp-client" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url

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
        assert f"state={rows[0].state}" in url


@pytest.mark.asyncio
async def test_start_oauth_returns_real_authorize_url_for_meta(client, _configure_gbp_and_meta):
    business_id, headers = await _signup_owner(client)
    resp = await client.post(
        f"/api/v1/businesses/{business_id}/connections/meta/oauth/start", headers=headers
    )
    assert resp.status_code == 200, resp.text
    url = resp.json()["authorize_url"]
    assert url.startswith("https://www.facebook.com/v19.0/dialog/oauth?")
    assert "client_id=test-meta-app" in url


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
async def test_callback_rejects_unknown_state(client):
    resp = await client.get(
        "/api/v1/oauth/callback/gbp", params={"state": "never-issued", "code": "x"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_callback_rejects_already_used_state(client):
    business_id, _headers = await _signup_owner(client)
    state = await _make_state(uuid.UUID(business_id), used=True)
    resp = await client.get("/api/v1/oauth/callback/gbp", params={"state": state, "code": "x"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_callback_rejects_expired_state(client):
    business_id, _headers = await _signup_owner(client)
    state = await _make_state(uuid.UUID(business_id), expires_in=timedelta(minutes=-1))
    resp = await client.get("/api/v1/oauth/callback/gbp", params={"state": state, "code": "x"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_callback_rejects_platform_mismatch(client):
    business_id, _headers = await _signup_owner(client)
    state = await _make_state(uuid.UUID(business_id), platform=PlatformName.meta)
    resp = await client.get("/api/v1/oauth/callback/gbp", params={"state": state, "code": "x"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_callback_rejects_provider_denied_authorization(client):
    business_id, _headers = await _signup_owner(client)
    state = await _make_state(uuid.UUID(business_id))
    resp = await client.get(
        "/api/v1/oauth/callback/gbp", params={"state": state, "error": "access_denied"}
    )
    assert resp.status_code == 400

    async with async_session_factory() as db:
        row = (await db.execute(select(OAuthState).where(OAuthState.state == state))).scalar_one()
        assert row.used_at is not None


@pytest.mark.asyncio
async def test_callback_rejects_missing_code(client):
    business_id, _headers = await _signup_owner(client)
    state = await _make_state(uuid.UUID(business_id))
    resp = await client.get("/api/v1/oauth/callback/gbp", params={"state": state})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_callback_exchanges_gbp_code_then_fails_cleanly_when_vault_rejects_credentials(
    client, _configure_gbp_and_meta, _mock_provider_token_exchange, _bogus_vault
):
    business_id, _headers = await _signup_owner(client)
    state = await _make_state(uuid.UUID(business_id), platform=PlatformName.gbp)

    resp = await client.get(
        "/api/v1/oauth/callback/gbp", params={"state": state, "code": "fake-code"}
    )
    assert resp.status_code == 502, resp.text

    async with async_session_factory() as db:
        state_row = (
            await db.execute(select(OAuthState).where(OAuthState.state == state))
        ).scalar_one()
        assert state_row.used_at is not None

        connections = list(
            (
                await db.execute(
                    select(PlatformConnection).where(
                        PlatformConnection.business_id == uuid.UUID(business_id)
                    )
                )
            ).scalars()
        )
        assert connections == []


@pytest.mark.asyncio
async def test_callback_exchanges_meta_code_then_fails_cleanly_when_vault_rejects_credentials(
    client, _configure_gbp_and_meta, _mock_provider_token_exchange, _bogus_vault
):
    business_id, _headers = await _signup_owner(client)
    state = await _make_state(uuid.UUID(business_id), platform=PlatformName.meta)

    resp = await client.get(
        "/api/v1/oauth/callback/meta", params={"state": state, "code": "fake-code"}
    )
    assert resp.status_code == 502, resp.text


@pytest.mark.asyncio
async def test_gbp_adapter_raises_not_implemented():
    import importlib

    gbp_mod = importlib.import_module("services.sync-engine.adapters.social.gbp")
    adapter = gbp_mod.GBPAdapter(access_token="fake")
    with pytest.raises(gbp_mod.GBPAdapterError):
        await adapter.get_insights("locations/1", datetime.now(UTC), datetime.now(UTC))
    with pytest.raises(gbp_mod.GBPAdapterError):
        await adapter.create_post("locations/1", "hello", None)
