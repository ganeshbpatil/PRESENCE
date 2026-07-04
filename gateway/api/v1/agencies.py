"""
gateway/api/v1/agencies.py

Agency console — cross-cutting per the docs' agency white-label channel
emphasis. Agency-scoped businesses list + a consolidated CSV export report
(PDF export is a separate, bigger undertaking not built in this pass —
CSV covers the same underlying data for now).
"""
from __future__ import annotations

import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db import get_db
from gateway.security import get_current_user
from shared.models.core import (
    Agency,
    AttributionCorrelation,
    Business,
    Review,
    User,
    UserRole,
)

router = APIRouter(prefix="/agencies", tags=["agencies"])


class BusinessSummary(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    tier: str
    subscription_status: str | None

    model_config = {"from_attributes": True}


async def _require_agency_access(agency_id: uuid.UUID, user: User, db: AsyncSession) -> Agency:
    agency = (
        await db.execute(select(Agency).where(Agency.id == agency_id))
    ).scalar_one_or_none()
    if agency is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agency not found")
    if user.agency_id != agency_id or user.role not in (
        UserRole.agency_admin,
        UserRole.agency_viewer,
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized for this agency")
    return agency


@router.get("/{agency_id}/businesses", response_model=list[BusinessSummary])
async def list_agency_businesses(
    agency_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Business]:
    await _require_agency_access(agency_id, user, db)
    result = await db.execute(select(Business).where(Business.agency_id == agency_id))
    return list(result.scalars().all())


@router.get("/{agency_id}/consolidated-report")
async def consolidated_report(
    agency_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    await _require_agency_access(agency_id, user, db)

    businesses = list(
        (await db.execute(select(Business).where(Business.agency_id == agency_id))).scalars()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "business_id",
            "name",
            "category",
            "tier",
            "review_count",
            "avg_rating",
            "latest_correlation_score",
            "signal_completeness_pct",
        ]
    )

    # Per-business rows, never blended across categories -- CLAUDE.md's
    # segment-level reporting rule (churn/CAC/ACV differ by category).
    for business in businesses:
        review_count, avg_rating = (
            await db.execute(
                select(func.count(Review.id), func.avg(Review.rating)).where(
                    Review.business_id == business.id
                )
            )
        ).one()

        latest_correlation = (
            await db.execute(
                select(AttributionCorrelation)
                .where(AttributionCorrelation.business_id == business.id)
                .order_by(AttributionCorrelation.computed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        writer.writerow(
            [
                str(business.id),
                business.name,
                business.category.value,
                business.tier.value,
                review_count or 0,
                f"{avg_rating:.2f}" if avg_rating is not None else "",
                latest_correlation.correlation_score if latest_correlation else "",
                latest_correlation.signal_completeness_pct if latest_correlation else "",
            ]
        )

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=agency-{agency_id}-report.csv"},
    )
