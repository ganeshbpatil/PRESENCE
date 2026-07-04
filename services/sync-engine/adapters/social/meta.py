"""
services/sync-engine/adapters/social/meta.py

Concrete Meta Graph API adapter — read Instagram/Facebook Page insights +
basic scheduled posting. Untestable end-to-end without a real connected
page access token (none configured in this environment).

NOTE on access tokens: SECURITY_ARCHITECTURE.md specifies
platform_connections.access_token_ref as a VAULT REFERENCE, never the raw
token — this adapter takes the token directly as a constructor arg,
assuming the caller already resolved the vault reference to a real token.
No vault (Doppler/Infisical/self-hosted Vault) is wired up in this pass —
that's a real gap against the security doc's intended design, flagged
rather than silently glossed over, not something to fake with a no-op
vault client.
"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx

from .base import PostResult, SocialAdapter, SocialInsight

_GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


class MetaAdapterError(Exception):
    pass


class MetaAdapter(SocialAdapter):
    provider_name = "meta"

    def __init__(self, access_token: str):
        self._access_token = access_token

    async def get_insights(
        self, external_id: str, period_start: datetime, period_end: datetime
    ) -> list[SocialInsight]:
        async with httpx.AsyncClient(base_url=_GRAPH_API_BASE, timeout=10.0) as client:
            resp = await client.get(
                f"/{external_id}/insights",
                params={
                    "metric": "page_views_total,page_impressions",
                    "since": int(period_start.timestamp()),
                    "until": int(period_end.timestamp()),
                    "access_token": self._access_token,
                },
            )
        if resp.status_code >= 300:
            raise MetaAdapterError(f"Meta insights fetch failed: {resp.status_code} {resp.text}")

        data = resp.json()
        insights: list[SocialInsight] = []
        for metric in data.get("data", []):
            for value_point in metric.get("values", []):
                insights.append(
                    SocialInsight(
                        platform="meta",
                        metric=metric.get("name", ""),
                        value=float(value_point.get("value", 0) or 0),
                        period_start=period_start,
                        period_end=period_end,
                    )
                )
        return insights

    async def create_post(
        self, external_id: str, content: str, media_url: str | None
    ) -> PostResult:
        payload = {"message": content, "access_token": self._access_token}
        if media_url:
            payload["link"] = media_url

        async with httpx.AsyncClient(base_url=_GRAPH_API_BASE, timeout=10.0) as client:
            resp = await client.post(f"/{external_id}/feed", data=payload)
        if resp.status_code >= 300:
            raise MetaAdapterError(f"Meta post failed: {resp.status_code} {resp.text}")

        data = resp.json()
        return PostResult(
            provider_post_id=data.get("id", ""), posted_at=datetime.now(UTC)
        )
