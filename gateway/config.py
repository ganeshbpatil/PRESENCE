"""
gateway/config.py

Centralized settings read from environment variables (.env locally,
container env in Docker/VPS) — see docs/PRESENCE/05_ENGINEERING/
BACKEND_STANDARDS.md: config via env vars only, never hardcoded.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me"

    database_url: str = "postgresql+asyncpg://presence:@postgres:5432/presence"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"


@lru_cache
def get_settings() -> Settings:
    return Settings()
