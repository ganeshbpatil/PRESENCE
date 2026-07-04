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
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db import get_db
from gateway.security import assert_valid_invite_code, get_current_user
from gateway.tenancy import require_agency_access
from shared.models.core import (
    Agency,
    AttributionCorrelation,
    Business,
    Review,
    User,
)

router = APIRouter(prefix="/agencies", tags=["agencies"])


class BusinessSummary(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    tier: str
    subscription_status: str | None

    model_config = {"from_attributes": True}


class AgencyCreate(BaseModel):
    name: str
    is_white_label: bool = False
    revenue_share_pct: Decimal | None = None
    # Required when settings.signup_invite_code is set (production) --
    # see gateway/security.py's assert_valid_invite_code.
    invite_code: str | None = None


class AgencyUpdate(BaseModel):
    # All optional -- PATCH semantics, only set fields are touched.
    name: str | None = None
    is_white_label: bool | None = None
    branding_config: dict | None = None
    revenue_share_pct: Decimal | None = None


class AgencyResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_white_label: bool
    branding_config: dict | None
    revenue_share_pct: Decimal | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("", response_model=AgencyResponse, status_code=status.HTTP_201_CREATED)
async def create_agency(body: AgencyCreate, db: AsyncSession = Depends(get_db)) -> Agency:
    # Mirrors businesses.py's create_business: unauthenticated by design
    # (an agency must exist before agency_admin signup can reference it),
    # gated by the same shared invite code instead.
    assert_valid_invite_code(body.invite_code)
    agency = Agency(
        name=body.name,
        is_white_label=body.is_white_label,
        revenue_share_pct=body.revenue_share_pct,
    )
    db.add(agency)
    await db.commit()
    await db.refresh(agency)
    return agency


@router.get("/{agency_id}", response_model=AgencyResponse)
async def get_agency(
    agency_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Agency:
    # Needed so an edit form has something to prefill -- previously the
    # only way to see an agency's own fields was the PATCH response.
    return await require_agency_access(agency_id, user, db)


@router.patch("/{agency_id}", response_model=AgencyResponse)
async def update_agency(
    agency_id: uuid.UUID,
    body: AgencyUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Agency:
    agency = await require_agency_access(agency_id, user, db, write=True)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(agency, field, value)
    await db.commit()
    await db.refresh(agency)
    return agency


@router.get("/{agency_id}/businesses", response_model=list[BusinessSummary])
async def list_agency_businesses(
    agency_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Business]:
    await require_agency_access(agency_id, user, db)
    result = await db.execute(select(Business).where(Business.agency_id == agency_id))
    return list(result.scalars().all())


@router.get("/{agency_id}/consolidated-report")
async def consolidated_report(
    agency_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    await require_agency_access(agency_id, user, db)

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
