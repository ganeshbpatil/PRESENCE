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
import string
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import httpx
from prometheus_client import Counter

AI_CACHE_HITS = Counter("ai_cache_hit_total", "AI orchestrator cache hits")
AI_CACHE_MISSES = Counter("ai_cache_miss_total", "AI orchestrator cache misses")

_PROMPTS_DIR = Path(__file__).parent / "prompts"

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_MODEL = "anthropic/claude-3-haiku"  # cheap default -- margin lever per AI.md
_ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
_ANTHROPIC_MODEL = "claude-3-haiku-20240307"
_ANTHROPIC_API_VERSION = "2023-06-01"


class AIProviderError(Exception):
    pass


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

    def __init__(
        self,
        cache: CacheBackend,
        default_provider: AIProvider,
        cache_ttl_seconds: int,
        openrouter_api_key: str = "",
        anthropic_api_key: str = "",
    ):
        self._cache = cache
        self._default_provider = default_provider
        self._cache_ttl = cache_ttl_seconds
        self._openrouter_api_key = openrouter_api_key
        self._anthropic_api_key = anthropic_api_key

    async def complete(self, req: AIRequest) -> AIResponse:
        if req.cacheable:
            key = _cache_key(req)
            cached = await self._cache.get(key)
            if cached is not None:
                AI_CACHE_HITS.inc()
                return AIResponse(
                    text=cached, provider_used=self._default_provider,
                    cache_hit=True, tokens_in=None, tokens_out=None,
                    cost_estimate_usd=0.0,
                )
            AI_CACHE_MISSES.inc()

        text, tokens_in, tokens_out, cost = await self._call_provider(req)

        if req.cacheable:
            await self._cache.set(_cache_key(req), text, self._cache_ttl)

        return AIResponse(
            text=text, provider_used=self._default_provider, cache_hit=False,
            tokens_in=tokens_in, tokens_out=tokens_out, cost_estimate_usd=cost,
        )

    async def _call_provider(self, req: AIRequest) -> tuple[str, int, int, float]:
        prompt_text = _render_prompt(req.prompt_template_id, req.variables)

        providers_in_order = [self._default_provider] + [
            p for p in AIProvider if p != self._default_provider
        ]
        last_error: Exception | None = None
        for provider in providers_in_order:
            try:
                if provider == AIProvider.OPENROUTER:
                    return await self._call_openrouter(prompt_text)
                return await self._call_anthropic(prompt_text)
            except AIProviderError as exc:
                last_error = exc
                continue  # fall through to the next provider (fallback)

        raise AIProviderError(f"All AI providers failed: {last_error}") from last_error

    async def _call_openrouter(self, prompt_text: str) -> tuple[str, int, int, float]:
        if not self._openrouter_api_key:
            raise AIProviderError("OPENROUTER_API_KEY not configured")

        async with httpx.AsyncClient(base_url=_OPENROUTER_BASE_URL, timeout=20.0) as client:
            resp = await client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self._openrouter_api_key}"},
                json={
                    "model": _OPENROUTER_MODEL,
                    "messages": [{"role": "user", "content": prompt_text}],
                },
            )
        if resp.status_code >= 300:
            raise AIProviderError(f"OpenRouter call failed: {resp.status_code} {resp.text}")

        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)
        cost = float(usage.get("total_cost", 0.0) or 0.0)
        return text, tokens_in, tokens_out, cost

    async def _call_anthropic(self, prompt_text: str) -> tuple[str, int, int, float]:
        if not self._anthropic_api_key:
            raise AIProviderError("ANTHROPIC_API_KEY not configured")

        async with httpx.AsyncClient(base_url=_ANTHROPIC_BASE_URL, timeout=20.0) as client:
            resp = await client.post(
                "/messages",
                headers={
                    "x-api-key": self._anthropic_api_key,
                    "anthropic-version": _ANTHROPIC_API_VERSION,
                },
                json={
                    "model": _ANTHROPIC_MODEL,
                    "max_tokens": 512,
                    "messages": [{"role": "user", "content": prompt_text}],
                },
            )
        if resp.status_code >= 300:
            raise AIProviderError(f"Anthropic call failed: {resp.status_code} {resp.text}")

        data = resp.json()
        text = "".join(block.get("text", "") for block in data.get("content", []))
        usage = data.get("usage", {})
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)
        # Anthropic doesn't return a cost figure directly; a real cost
        # estimate needs a per-model $/token rate table (same pattern as
        # the WhatsApp adapter's estimate_cost_inr) -- not built in this
        # pass, so this is left at 0.0 rather than guessed.
        return text, tokens_in, tokens_out, 0.0


def _render_prompt(template_id: str, variables: dict) -> str:
    path = _PROMPTS_DIR / f"{template_id}.txt"
    if not path.exists():
        raise AIProviderError(f"Unknown prompt template: {template_id!r}")
    template = string.Template(path.read_text())
    return template.safe_substitute(**{k: str(v) for k, v in variables.items()})
