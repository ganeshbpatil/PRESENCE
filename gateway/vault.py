"""
gateway/vault.py

FastAPI dependency wiring for shared.secrets.vault_client -- lets tests
override get_vault_client() with a fake the same way they override
get_db/get_settings, instead of every route hitting a real Vault instance.
"""
from __future__ import annotations

from fastapi import Depends

from gateway.config import Settings, get_settings
from shared.secrets.vault_client import VaultClient


def get_vault_client(settings: Settings = Depends(get_settings)) -> VaultClient:
    return VaultClient(
        addr=settings.vault_addr,
        role_id=settings.vault_role_id,
        secret_id=settings.vault_secret_id,
        kv_mount=settings.vault_kv_mount,
    )
