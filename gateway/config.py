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

    # Meta OAuth -- see gateway/api/v1/oauth.py. meta_redirect_uri must be
    # the exact URI registered in the Meta App's console (a single fixed
    # path, e.g. https://<domain>/api/v1/oauth/callback/meta -- NOT
    # templated with a business_id, Meta doesn't support wildcard redirect
    # URIs; tenant context rides in the OAuth `state` param instead).
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_webhook_verify_token: str = ""
    meta_redirect_uri: str = ""

    # GBP OAuth -- see gateway/api/v1/oauth.py. gbp_redirect_uri must be
    # the exact URI registered in the Google Cloud OAuth client (a single
    # fixed path, e.g. https://<domain>/api/v1/oauth/callback/gbp -- same
    # no-wildcard caveat as meta_redirect_uri above). Note the *data* API
    # calls (get_insights/create_post against the actual Business Profile
    # API) are still a deliberate stub in
    # services/sync-engine/adapters/social/gbp.py -- that surface is
    # under-documented enough to need a real test app before writing real
    # calls; the OAuth token exchange itself is boilerplate, identical
    # across all Google APIs, and safe to implement now.
    gbp_client_id: str = ""
    gbp_client_secret: str = ""
    gbp_redirect_uri: str = ""

    vault_addr: str = "http://vault:8200"
    vault_role_id: str = ""
    vault_secret_id: str = ""
    vault_kv_mount: str = "presence-secrets"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@presence.local"

    # Comma-separated origins the admin-panel frontend is served from (e.g.
    # "http://localhost:3000,https://app.presence.yourdomain.com") -- empty
    # means no cross-origin frontend is configured yet.
    cors_allowed_origins: str = ""

    # Shared secret required to create a Business or Agency (both are
    # otherwise-unauthenticated bootstrap endpoints -- a business/agency
    # must exist before a user can sign up referencing it). Empty means
    # the check is skipped entirely -- set this in production so the
    # public API can't be used to spin up arbitrary shells. Distribute
    # this one code to whoever should be able to onboard an
    # agency/business (sales calls, agency partners); rotate by changing
    # the env var.
    signup_invite_code: str = ""

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
