"""
gateway/api/v1/health.py

Readiness check for the gateway service — verifies the dependencies
docker-compose.yml declares as `service_healthy` for this container
(Postgres, Redis) are actually reachable, not just that the process is up.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.config import get_settings
from gateway.db import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict:
    settings = get_settings()

    await db.execute(text("SELECT 1"))

    redis_client = Redis.from_url(settings.redis_url)
    try:
        await redis_client.ping()
    finally:
        await redis_client.aclose()

    return {"status": "ok", "database": "ok", "redis": "ok"}
