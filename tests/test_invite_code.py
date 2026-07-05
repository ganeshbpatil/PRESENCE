"""
assert_valid_invite_code (gateway/security.py) gates the two
otherwise-unauthenticated bootstrap endpoints (POST /businesses,
POST /agencies). Monkeypatches gateway.security.get_settings directly
(not app.dependency_overrides -- neither route declares a Settings
dependency, assert_valid_invite_code calls the module-level function
itself) so these pass regardless of whether SIGNUP_INVITE_CODE happens to
be set in the environment running the suite.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

import gateway.security as security_module
from gateway.config import Settings
from gateway.main import app
from shared.models.core import BusinessCategory, BusinessTier


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _force_invite_code(monkeypatch: pytest.MonkeyPatch, code: str) -> None:
    forced = Settings(signup_invite_code=code)
    monkeypatch.setattr(security_module, "get_settings", lambda: forced)


@pytest.mark.asyncio
async def test_business_create_accepts_correct_invite_code(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_invite_code(monkeypatch, "the-real-code")
    resp = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"Invite Code Test {uuid.uuid4()}",
            "category": BusinessCategory.salon_spa_gym.value,
            "tier": BusinessTier.starter.value,
            "invite_code": "the-real-code",
        },
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_business_create_rejects_wrong_invite_code(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_invite_code(monkeypatch, "the-real-code")
    resp = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"Invite Code Test {uuid.uuid4()}",
            "category": BusinessCategory.salon_spa_gym.value,
            "tier": BusinessTier.starter.value,
            "invite_code": "wrong-code",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_business_create_rejects_missing_invite_code_when_configured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_invite_code(monkeypatch, "the-real-code")
    resp = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"Invite Code Test {uuid.uuid4()}",
            "category": BusinessCategory.salon_spa_gym.value,
            "tier": BusinessTier.starter.value,
            # invite_code omitted entirely
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_business_create_skips_check_when_unconfigured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_invite_code(monkeypatch, "")
    resp = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"Invite Code Test {uuid.uuid4()}",
            "category": BusinessCategory.salon_spa_gym.value,
            "tier": BusinessTier.starter.value,
        },
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_agency_create_rejects_wrong_invite_code(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_invite_code(monkeypatch, "the-real-code")
    resp = await client.post(
        "/api/v1/agencies",
        json={"name": f"Invite Code Agency {uuid.uuid4()}", "invite_code": "wrong-code"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agency_create_accepts_correct_invite_code(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_invite_code(monkeypatch, "the-real-code")
    resp = await client.post(
        "/api/v1/agencies",
        json={"name": f"Invite Code Agency {uuid.uuid4()}", "invite_code": "the-real-code"},
    )
    assert resp.status_code == 201, resp.text


# Signup itself: every signup here references an already-existing
# business_id/agency_id, and those IDs aren't secret (they appear in
# ordinary API responses) -- without this gate, anyone who's seen an
# agency_id could self-register as agency_admin for it. This was a real,
# unguarded gap (see CLAUDE.md's audit history) -- assert_valid_invite_code
# is now called from signup() the same way it's called from business/agency
# creation.


@pytest.mark.asyncio
async def test_signup_agency_admin_rejects_missing_invite_code_when_configured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_invite_code(monkeypatch, "the-real-code")
    agency = await client.post(
        "/api/v1/agencies",
        json={"name": f"Signup Gate Agency {uuid.uuid4()}", "invite_code": "the-real-code"},
    )
    agency_id = agency.json()["id"]

    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"attacker-{uuid.uuid4()}@example.com",
            "password": "correct-horse-battery",
            "role": "agency_admin",
            "agency_id": agency_id,
            # invite_code omitted -- this is the privilege-escalation path:
            # knowing agency_id alone must not be enough.
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_signup_agency_admin_rejects_wrong_invite_code(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_invite_code(monkeypatch, "the-real-code")
    agency = await client.post(
        "/api/v1/agencies",
        json={"name": f"Signup Gate Agency {uuid.uuid4()}", "invite_code": "the-real-code"},
    )
    agency_id = agency.json()["id"]

    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"attacker-{uuid.uuid4()}@example.com",
            "password": "correct-horse-battery",
            "role": "agency_admin",
            "agency_id": agency_id,
            "invite_code": "wrong-code",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_signup_agency_admin_accepts_correct_invite_code(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_invite_code(monkeypatch, "the-real-code")
    agency = await client.post(
        "/api/v1/agencies",
        json={"name": f"Signup Gate Agency {uuid.uuid4()}", "invite_code": "the-real-code"},
    )
    agency_id = agency.json()["id"]

    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"legit-{uuid.uuid4()}@example.com",
            "password": "correct-horse-battery",
            "role": "agency_admin",
            "agency_id": agency_id,
            "invite_code": "the-real-code",
        },
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_signup_smb_owner_rejects_missing_invite_code_when_configured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_invite_code(monkeypatch, "the-real-code")
    business = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"Signup Gate Business {uuid.uuid4()}",
            "category": BusinessCategory.salon_spa_gym.value,
            "tier": BusinessTier.starter.value,
            "invite_code": "the-real-code",
        },
    )
    business_id = business.json()["id"]

    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"attacker-{uuid.uuid4()}@example.com",
            "password": "correct-horse-battery",
            "role": "smb_owner",
            "business_id": business_id,
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_signup_skips_invite_check_when_unconfigured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _force_invite_code(monkeypatch, "")
    business = await client.post(
        "/api/v1/businesses",
        json={
            "name": f"Signup Gate Business {uuid.uuid4()}",
            "category": BusinessCategory.salon_spa_gym.value,
            "tier": BusinessTier.starter.value,
        },
    )
    business_id = business.json()["id"]

    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"owner-{uuid.uuid4()}@example.com",
            "password": "correct-horse-battery",
            "role": "smb_owner",
            "business_id": business_id,
        },
    )
    assert resp.status_code == 201, resp.text
