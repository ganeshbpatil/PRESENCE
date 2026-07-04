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

    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 30

    ai_default_provider: str = "openrouter"
    ai_cache_ttl_seconds: int = 86400
    openrouter_api_key: str = ""
    anthropic_api_key: str = ""

    gallabox_api_key: str = ""
    gallabox_api_secret: str = ""
    gallabox_webhook_secret: str = ""

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_webhook_verify_token: str = ""

    vault_addr: str = "http://vault:8200"
    vault_role_id: str = ""
    vault_secret_id: str = ""
    vault_kv_mount: str = "presence-secrets"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@presence.local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
