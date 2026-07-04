"""
services/sync-engine/adapters/whatsapp/factory.py

Provider factory per base.py's contract: a BSP swap must be a config
change + new adapter file, zero changes to calling code. Calling code
depends only on get_adapter(), never imports a concrete adapter class
directly.

Takes explicit primitive credentials, not a gateway.config.Settings object
— services/* must never import from gateway/* (CODING_STANDARDS.md's
clean-separation rule is gateway -> services -> shared/models, one
direction only). The caller (a gateway router) reads its own Settings and
passes values through.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from .base import WhatsAppBSPAdapter
from .gallabox import GallaboxAdapter


def get_adapter(
    provider: str,
    db: AsyncSession,
    *,
    gallabox_api_key: str,
    gallabox_api_secret: str,
    gallabox_webhook_secret: str,
) -> WhatsAppBSPAdapter:
    if provider == "gallabox":
        return GallaboxAdapter(
            api_key=gallabox_api_key,
            api_secret=gallabox_api_secret,
            webhook_secret=gallabox_webhook_secret,
            db=db,
        )
    # Gupshup/Interakt are stubs per CLAUDE.md principle #2 — add a new
    # adapter file + a branch here when one is actually implemented.
    raise ValueError(f"Unknown WhatsApp BSP provider: {provider!r}")
