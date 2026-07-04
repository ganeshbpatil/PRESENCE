"""
services/ai-orchestrator/cache.py

Redis-backed CacheBackend — reuses the existing Redis instance already
running for Celery, per router.py's design-intent comment ("don't add a
new cache dependency").
"""
from __future__ import annotations

from redis.asyncio import Redis

from .router import CacheBackend


class RedisCacheBackend(CacheBackend):
    def __init__(self, redis_url: str):
        self._redis_url = redis_url

    async def get(self, key: str) -> str | None:
        client = Redis.from_url(self._redis_url)
        try:
            value = await client.get(key)
        finally:
            await client.aclose()
        if value is None:
            return None
        return value.decode() if isinstance(value, bytes) else value

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        client = Redis.from_url(self._redis_url)
        try:
            await client.set(key, value, ex=ttl_seconds)
        finally:
            await client.aclose()
