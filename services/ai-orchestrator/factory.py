"""
services/ai-orchestrator/factory.py

Per-request AIOrchestrator construction — mirrors sync-engine's WhatsApp
adapter factory pattern. Feature code should call get_orchestrator()
rather than constructing AIOrchestrator/RedisCacheBackend directly.

Takes explicit primitive config, not a gateway.config.Settings object —
services/* must never import from gateway/* (see the WhatsApp factory's
identical note on the clean-separation rule).
"""
from __future__ import annotations

from .cache import RedisCacheBackend
from .router import AIOrchestrator, AIProvider


def get_orchestrator(
    *,
    redis_url: str,
    default_provider: str,
    cache_ttl_seconds: int,
    openrouter_api_key: str,
    anthropic_api_key: str,
) -> AIOrchestrator:
    provider = (
        AIProvider.ANTHROPIC_DIRECT
        if default_provider == AIProvider.ANTHROPIC_DIRECT.value
        else AIProvider.OPENROUTER
    )
    return AIOrchestrator(
        cache=RedisCacheBackend(redis_url),
        default_provider=provider,
        cache_ttl_seconds=cache_ttl_seconds,
        openrouter_api_key=openrouter_api_key,
        anthropic_api_key=anthropic_api_key,
    )
