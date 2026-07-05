"""
gateway/api/v1/dashboard.py

Read-only aggregated KPIs + chart data for the admin panel's dashboard/
overview page. No new access model -- reuses require_business_access/
require_agency_access, the same row-level tenancy check every other
router uses (see gateway/tenancy.py).
"""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db import get_db
from gateway.security import get_current_user
from gateway.tenancy import require_agency_access, require_business_access
from shared.models.core import Business, Review, User

router = APIRouter(tags=["dashboard"])

# Fixed 30-day window for the Review Volume chart -- long enough to show a
# trend, short enough that a new business isn't staring at 11 empty months.
_VOLUME_WINDOW_DAYS = 30


class ReviewVolumePoint(BaseModel):
    date: date
    count: int


class RatingBucket(BaseModel):
    rating: int
    count: int


class DashboardStats(BaseModel):
    avg_rating: float | None
    reviews_this_month: int
    pending_replies: int
    reply_rate_pct: float | None
    review_volume: list[ReviewVolumePoint]
    rating_distribution: list[RatingBucket]


class BusinessDashboard(DashboardStats):
    business_id: uuid.UUID


class AgencyDashboard(DashboardStats):
    agency_id: uuid.UUID
    active_businesses: int
    total_businesses: int


async def _stats_for_business_ids(
    business_ids: list[uuid.UUID], db: AsyncSession
) -> DashboardStats:
    empty_volume = _volume_skeleton()
    empty_ratings = [RatingBucket(rating=r, count=0) for r in range(1, 6)]

    if not business_ids:
        return DashboardStats(
            avg_rating=None,
            reviews_this_month=0,
            pending_replies=0,
            reply_rate_pct=None,
            review_volume=empty_volume,
            rating_distribution=empty_ratings,
        )

    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    window_start = now - timedelta(days=_VOLUME_WINDOW_DAYS - 1)

    reviews = list(
        (
            await db.execute(
                select(Review.rating, Review.created_at, Review.response_sent_at).where(
                    Review.business_id.in_(business_ids)
                )
            )
        ).all()
    )

    total = len(reviews)
    rated = [r.rating for r in reviews if r.rating is not None]
    replied = sum(1 for r in reviews if r.response_sent_at is not None)
    pending_replies = total - replied
    reviews_this_month = sum(1 for r in reviews if r.created_at >= month_start)

    day_counts = Counter(
        r.created_at.astimezone(UTC).date() for r in reviews if r.created_at >= window_start
    )
    window_start_day = window_start.date()
    review_volume = [
        ReviewVolumePoint(
            date=window_start_day + timedelta(days=i),
            count=day_counts.get(window_start_day + timedelta(days=i), 0),
        )
        for i in range(_VOLUME_WINDOW_DAYS)
    ]

    rating_counts = Counter(rated)
    rating_distribution = [
        RatingBucket(rating=r, count=rating_counts.get(r, 0)) for r in range(1, 6)
    ]

    return DashboardStats(
        avg_rating=(sum(rated) / len(rated)) if rated else None,
        reviews_this_month=reviews_this_month,
        pending_replies=pending_replies,
        reply_rate_pct=(replied / total * 100) if total else None,
        review_volume=review_volume,
        rating_distribution=rating_distribution,
    )


def _volume_skeleton() -> list[ReviewVolumePoint]:
    now = datetime.now(UTC)
    window_start_day = (now - timedelta(days=_VOLUME_WINDOW_DAYS - 1)).date()
    return [
        ReviewVolumePoint(date=window_start_day + timedelta(days=i), count=0)
        for i in range(_VOLUME_WINDOW_DAYS)
    ]


@router.get("/businesses/{business_id}/dashboard", response_model=BusinessDashboard)
async def business_dashboard(
    business_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BusinessDashboard:
    await require_business_access(business_id, user, db)
    stats = await _stats_for_business_ids([business_id], db)
    return BusinessDashboard(business_id=business_id, **stats.model_dump())


@router.get("/agencies/{agency_id}/dashboard", response_model=AgencyDashboard)
async def agency_dashboard(
    agency_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgencyDashboard:
    await require_agency_access(agency_id, user, db)
    businesses = list(
        (
            await db.execute(select(Business).where(Business.agency_id == agency_id))
        ).scalars()
    )
    stats = await _stats_for_business_ids([b.id for b in businesses], db)
    return AgencyDashboard(
        agency_id=agency_id,
        active_businesses=sum(1 for b in businesses if b.churned_at is None),
        total_businesses=len(businesses),
        **stats.model_dump(),
    )
