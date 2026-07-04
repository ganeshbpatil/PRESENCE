"""
services/sync-engine/adapters/social/gbp.py

Google Business Profile adapter skeleton -- implements the SocialAdapter
interface shape but neither method makes a real API call yet. Deliberate:
building the actual Google Business Profile API integration (get_insights
against the Performance API, create_post against the Local Posts API)
requires a verified Google Cloud project with Business Profile API access
enabled and a real OAuth client, neither of which exist yet (see
gateway/config.py's gbp_client_id/gbp_client_secret, both empty) -- do not
guess at Google's endpoint URLs, request/response shapes, or required
scopes without a way to test against the real API. Wire the real calls in
here once gateway/api/v1/oauth.py's callback can actually exchange a code
for a token.
"""
from __future__ import annotations

from datetime import datetime

from .base import PostResult, SocialAdapter, SocialInsight


class GBPAdapterError(Exception):
    pass


class GBPAdapter(SocialAdapter):
    provider_name = "gbp"

    def __init__(self, access_token: str):
        self._access_token = access_token

    async def get_insights(
        self, external_id: str, period_start: datetime, period_end: datetime
    ) -> list[SocialInsight]:
        raise GBPAdapterError(
            "GBP adapter not yet implemented against the real API -- needs a "
            "verified Business Profile API endpoint/response shape before "
            "building real HTTP calls, see this module's docstring"
        )

    async def create_post(
        self, external_id: str, content: str, media_url: str | None
    ) -> PostResult:
        raise GBPAdapterError(
            "GBP adapter not yet implemented against the real API -- needs a "
            "verified Local Posts API endpoint/scope before building real "
            "HTTP calls, see this module's docstring"
        )
