"""
shared/secrets/vault_client.py

Resolves PlatformConnection.access_token_ref to a real platform access
token via a self-hosted HashiCorp Vault (see docs/PRESENCE/03_ARCHITECTURE/
SECURITY_ARCHITECTURE.md's Secrets Management section) -- no raw platform
token is ever stored in Postgres, only a KV v2 path reference.

Auth is AppRole (role_id + secret_id), not a static root token -- the
AppRole's policy is scoped to the presence-secrets/data/platform-
connections/* path only (see scripts/vault-init.sh, run once by hand).

Takes explicit primitive config, not a gateway.config.Settings object --
services/* must never import from gateway/*, same rule as the WhatsApp
adapter factory. Feature code should call get_vault_client() rather than
constructing VaultClient directly.
"""
from __future__ import annotations

import time
import uuid

import httpx


class VaultError(Exception):
    """Vault unreachable, sealed, or the ref doesn't resolve. Callers must
    treat this the same as a platform sync failure (CLAUDE.md principle
    #1: the product degrades to read-only, it does not crash) -- never let
    a VaultError propagate into a 500 or a crashed Celery task uncaught."""


class VaultClient:
    def __init__(
        self,
        addr: str,
        role_id: str,
        secret_id: str,
        kv_mount: str = "presence-secrets",
        timeout_seconds: float = 5.0,
    ):
        self._addr = addr.rstrip("/")
        self._role_id = role_id
        self._secret_id = secret_id
        self._kv_mount = kv_mount
        self._timeout = timeout_seconds
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    @staticmethod
    def ref_for(business_id: uuid.UUID, platform: str) -> str:
        """KV v2 path under the configured mount -- not a full Vault URL,
        so refs stored in Postgres stay valid if the mount ever moves."""
        return f"platform-connections/{business_id}/{platform}"

    async def _client_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token

        async with httpx.AsyncClient(base_url=self._addr, timeout=self._timeout) as client:
            try:
                resp = await client.post(
                    "/v1/auth/approle/login",
                    json={"role_id": self._role_id, "secret_id": self._secret_id},
                )
            except httpx.HTTPError as exc:
                raise VaultError(f"Vault unreachable at {self._addr}: {exc}") from exc

        if resp.status_code >= 300:
            raise VaultError(f"AppRole login failed: {resp.status_code} {resp.text}")

        auth = resp.json()["auth"]
        self._token = auth["client_token"]
        # Refresh a little before actual expiry so a request never races a
        # just-expired token.
        self._token_expires_at = time.monotonic() + max(auth["lease_duration"] - 30, 0)
        return self._token

    async def resolve(self, ref: str, key: str = "access_token") -> str:
        """Read one named field behind a vault reference (default:
        access_token). Use key="refresh_token" for the OAuth scaffold's
        refresh_token_ref -- both fields live at the SAME ref, written
        together by store() (see its docstring for why)."""
        token = await self._client_token()
        async with httpx.AsyncClient(base_url=self._addr, timeout=self._timeout) as client:
            try:
                resp = await client.get(
                    f"/v1/{self._kv_mount}/data/{ref}",
                    headers={"X-Vault-Token": token},
                )
            except httpx.HTTPError as exc:
                raise VaultError(f"Vault unreachable at {self._addr}: {exc}") from exc

        if resp.status_code == 404:
            raise VaultError(f"No secret at vault ref {ref!r}")
        if resp.status_code >= 300:
            raise VaultError(f"Vault read failed: {resp.status_code} {resp.text}")

        try:
            return resp.json()["data"]["data"][key]
        except (KeyError, TypeError) as exc:
            raise VaultError(f"Malformed secret at vault ref {ref!r}") from exc

    async def store(self, ref: str, **fields: str) -> None:
        """Write (or overwrite) one or more named fields behind a vault
        reference, e.g. store(ref, access_token=..., refresh_token=...).

        Vault KV v2's write endpoint REPLACES the entire secret version,
        it does not merge -- calling store(ref, access_token=...) and
        later store(ref, refresh_token=...) as two separate calls would
        silently wipe out whichever field was written first. Always write
        every field you have in one call (natural for an OAuth token
        exchange response, which returns access_token + refresh_token
        together)."""
        token = await self._client_token()
        async with httpx.AsyncClient(base_url=self._addr, timeout=self._timeout) as client:
            try:
                resp = await client.post(
                    f"/v1/{self._kv_mount}/data/{ref}",
                    headers={"X-Vault-Token": token},
                    json={"data": fields},
                )
            except httpx.HTTPError as exc:
                raise VaultError(f"Vault unreachable at {self._addr}: {exc}") from exc

        if resp.status_code >= 300:
            raise VaultError(f"Vault write failed: {resp.status_code} {resp.text}")


def get_vault_client(
    *,
    addr: str,
    role_id: str,
    secret_id: str,
    kv_mount: str = "presence-secrets",
) -> VaultClient:
    return VaultClient(addr=addr, role_id=role_id, secret_id=secret_id, kv_mount=kv_mount)
