"""
services/ai-orchestrator/router.py

Cache-first, model-agnostic AI call routing. This is the single biggest
lever on gross margin (see unit economics in the diligence memo — AI cost
is one of the few controllable line items). Feature code NEVER calls
OpenRouter/Anthropic SDKs directly — everything routes through here so
caching and provider-switching are enforced structurally, not by convention.

Design intent for the first Claude Code session on this file:
- Cache key should be a hash of (prompt_template_id + normalized_variables),
  NOT the raw prompt string — this lets semantically-identical requests
  (e.g. "draft a response to a 5-star review with no text") hit cache even
  if surrounding context differs slightly.
- Cache TTL from AI_CACHE_TTL_SECONDS env var, backed by Redis (already in
  the stack for Celery — reuse it, don't add a new cache dependency).
- Track cache hit rate as a first-class metric (see docs/build-roadmap.md
  Stage 11 observability table — <60% hit rate is an alert threshold, not
  just a nice-to-have dashboard number).
"""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class AIProvider(str, Enum):
    OPENROUTER = "openrouter"
    ANTHROPIC_DIRECT = "anthropic_direct"


@dataclass
class AIRequest:
    prompt_template_id: str  # e.g. "review_response_draft_v1" — versioned, see prompts/
    variables: dict          # template variables, order-independent for cache-key purposes
    business_id: str
    cacheable: bool = True   # set False only for genuinely novel-generation tasks


@dataclass
class AIResponse:
    text: str
    provider_used: AIProvider
    cache_hit: bool
    tokens_in: int | None
    tokens_out: int | None
    cost_estimate_usd: float | None


def _cache_key(req: AIRequest) -> str:
    """
    Deterministic cache key from template + variables, NOT raw prompt text.
    Sort keys so variable-order never causes a false cache miss.
    """
    payload = json.dumps(
        {"template": req.prompt_template_id, "vars": req.variables},
        sort_keys=True,
    )
    return f"ai_cache:{hashlib.sha256(payload.encode()).hexdigest()}"


class CacheBackend(ABC):
    @abstractmethod
    async def get(self, key: str) -> str | None: ...
    @abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: int) -> None: ...


class AIOrchestrator:
    """
    Usage from feature code:

        result = await orchestrator.complete(AIRequest(
            prompt_template_id="review_response_draft_v1",
            variables={"rating": 5, "review_text": "...", "business_name": "..."},
            business_id=str(business.id),
        ))

    Feature code never touches provider SDKs, cache logic, or cost
    calculation directly — all of that lives here so it can be audited
    and optimized in one place as usage scales.
    """

    def __init__(self, cache: CacheBackend, default_provider: AIProvider, cache_ttl_seconds: int):
        self._cache = cache
        self._default_provider = default_provider
        self._cache_ttl = cache_ttl_seconds
        # cache_hit_total / cache_miss_total should be Prometheus counters,
        # incremented in complete() below — wire this to the observability
        # stack in docs/build-roadmap.md Stage 11 before going to pilot.

    async def complete(self, req: AIRequest) -> AIResponse:
        if req.cacheable:
            key = _cache_key(req)
            cached = await self._cache.get(key)
            if cached is not None:
                return AIResponse(
                    text=cached, provider_used=self._default_provider,
                    cache_hit=True, tokens_in=None, tokens_out=None,
                    cost_estimate_usd=0.0,
                )

        text, tokens_in, tokens_out, cost = await self._call_provider(req)

        if req.cacheable:
            await self._cache.set(_cache_key(req), text, self._cache_ttl)

        return AIResponse(
            text=text, provider_used=self._default_provider, cache_hit=False,
            tokens_in=tokens_in, tokens_out=tokens_out, cost_estimate_usd=cost,
        )

    async def _call_provider(self, req: AIRequest) -> tuple[str, int, int, float]:
        # TODO: render the template from prompts/ using req.variables, call
        # the configured provider (OpenRouter primary, Anthropic direct as
        # fallback per AI_DEFAULT_PROVIDER), return (text, tokens_in,
        # tokens_out, cost_estimate_usd). Provider-switch logic belongs here
        # ONLY — never scattered into feature code.
        raise NotImplementedError("Wire provider call here")
