"""
Fixture-based unit tests for shared/secrets/vault_client.py, using
httpx.MockTransport to simulate Vault's HTTP API (AppRole login + KV v2
read/write) -- no real Vault instance needed, matching the "fixture-based
unit test using recorded sample responses" convention the README requires
for BSP/platform adapters.
"""
from __future__ import annotations

import uuid

import httpx
import pytest

from shared.secrets.vault_client import VaultClient, VaultError

_ROLE_ID = "test-role-id"
_SECRET_ID = "test-secret-id"
_CLIENT_TOKEN = "s.fake-client-token"


def _vault(monkeypatch, handler) -> VaultClient:
    """Routes every httpx.AsyncClient the VaultClient constructs through a
    MockTransport instead of a real socket. VaultClient builds a fresh
    AsyncClient per call (no shared session), so we patch the constructor
    itself rather than injecting a transport instance."""
    real_async_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    return VaultClient(addr="http://vault:8200", role_id=_ROLE_ID, secret_id=_SECRET_ID)


def _approle_login_response(request: httpx.Request) -> httpx.Response:
    body = request.read()
    assert _ROLE_ID.encode() in body
    assert _SECRET_ID.encode() in body
    return httpx.Response(
        200,
        json={"auth": {"client_token": _CLIENT_TOKEN, "lease_duration": 3600}},
    )


@pytest.mark.asyncio
async def test_resolve_returns_token_on_successful_read(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/auth/approle/login":
            return _approle_login_response(request)
        assert request.headers["X-Vault-Token"] == _CLIENT_TOKEN
        assert request.url.path == "/v1/presence-secrets/data/platform-connections/biz-1/meta"
        return httpx.Response(200, json={"data": {"data": {"access_token": "raw-meta-token"}}})

    vault = _vault(monkeypatch, handler)
    token = await vault.resolve("platform-connections/biz-1/meta")
    assert token == "raw-meta-token"


@pytest.mark.asyncio
async def test_resolve_raises_vault_error_on_missing_ref(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/auth/approle/login":
            return _approle_login_response(request)
        return httpx.Response(404, json={"errors": []})

    vault = _vault(monkeypatch, handler)
    with pytest.raises(VaultError):
        await vault.resolve("platform-connections/biz-1/meta")


@pytest.mark.asyncio
async def test_resolve_raises_vault_error_on_malformed_secret(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/auth/approle/login":
            return _approle_login_response(request)
        return httpx.Response(200, json={"data": {"data": {"wrong_key": "oops"}}})

    vault = _vault(monkeypatch, handler)
    with pytest.raises(VaultError):
        await vault.resolve("platform-connections/biz-1/meta")


@pytest.mark.asyncio
async def test_store_writes_token_under_expected_path(monkeypatch):
    written = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/auth/approle/login":
            return _approle_login_response(request)
        assert request.url.path == "/v1/presence-secrets/data/platform-connections/biz-2/meta"
        written["body"] = request.read()
        return httpx.Response(200, json={"data": {"version": 1}})

    vault = _vault(monkeypatch, handler)
    await vault.store("platform-connections/biz-2/meta", access_token="raw-token-to-store")
    assert b"raw-token-to-store" in written["body"]


@pytest.mark.asyncio
async def test_store_writes_multiple_fields_in_one_call(monkeypatch):
    """KV v2 replaces the whole secret version on write -- access_token and
    refresh_token must go in the SAME store() call or the second call
    would silently wipe the first (see store()'s docstring)."""
    written = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/auth/approle/login":
            return _approle_login_response(request)
        written["body"] = request.read()
        return httpx.Response(200, json={"data": {"version": 1}})

    vault = _vault(monkeypatch, handler)
    await vault.store(
        "platform-connections/biz-3/gbp",
        access_token="access-tok",
        refresh_token="refresh-tok",
    )
    assert b"access-tok" in written["body"]
    assert b"refresh-tok" in written["body"]


@pytest.mark.asyncio
async def test_resolve_reads_a_named_key_other_than_access_token(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/auth/approle/login":
            return _approle_login_response(request)
        return httpx.Response(
            200,
            json={"data": {"data": {"access_token": "a", "refresh_token": "r"}}},
        )

    vault = _vault(monkeypatch, handler)
    token = await vault.resolve("platform-connections/biz-3/gbp", key="refresh_token")
    assert token == "r"


@pytest.mark.asyncio
async def test_login_failure_raises_vault_error_and_never_reaches_kv_call(monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(400, json={"errors": ["invalid role or secret ID"]})

    vault = _vault(monkeypatch, handler)
    with pytest.raises(VaultError):
        await vault.resolve("platform-connections/biz-1/meta")
    assert calls == ["/v1/auth/approle/login"]


@pytest.mark.asyncio
async def test_client_token_is_reused_across_calls_within_lease(monkeypatch):
    login_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_calls
        if request.url.path == "/v1/auth/approle/login":
            login_calls += 1
            return _approle_login_response(request)
        return httpx.Response(200, json={"data": {"data": {"access_token": "tok"}}})

    vault = _vault(monkeypatch, handler)
    await vault.resolve("platform-connections/biz-1/meta")
    await vault.resolve("platform-connections/biz-1/meta")
    assert login_calls == 1  # second call reused the cached client token


def test_ref_for_is_stable_and_provider_agnostic():
    business_id = uuid.uuid4()
    assert VaultClient.ref_for(business_id, "meta") == f"platform-connections/{business_id}/meta"
