"""
services/sync-engine/adapters/social/base.py

Narrow scope per 06_MODULES/SOCIAL.md: read Meta/Instagram presence data
(attribution-signal input) + basic scheduled posting only. Explicitly NOT
in scope: ads management (Meta Ads Manager already does this — do not
rebuild it), LinkedIn (no validated segment demand per the diligence
memo's Phase 0 research).

GBP/Meta are sync sources, never system of record (CLAUDE.md principle
#1) — get_insights() feeds attribution-engine's proxy signals, it is never
treated as authoritative business data.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SocialInsight:
    platform: str
    metric: str  # e.g. "page_views_total", "impressions"
    value: float
    period_start: datetime
    period_end: datetime


@dataclass
class PostResult:
    provider_post_id: str
    posted_at: datetime


class SocialAdapter(ABC):
    """Abstract base — one subclass per platform. Never instantiate directly."""

    provider_name: str

    @abstractmethod
    async def get_insights(
        self, external_id: str, period_start: datetime, period_end: datetime
    ) -> list[SocialInsight]:
        """Read-only insight pull — feeds attribution-engine's proxy
        signals. Never treated as system of record."""
        ...

    @abstractmethod
    async def create_post(
        self, external_id: str, content: str, media_url: str | None
    ) -> PostResult:
        """Basic scheduled posting only — no ads, no boosted posts, no
        campaign management."""
        ...
