"""
gateway/api/v1/attribution.py

Attribution engine endpoints — API_STANDARDS.md calls for these to be
versioned/namespaced separately from sync-engine endpoints so the service
can be extracted/licensed independently later. Both share /api/v1 for now
in this pass (a full separate API version is a bigger undertaking than
this build); the isolation that actually matters (no shared DB tables,
separate service directory) is already in place.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db import get_db
from gateway.security import get_current_user
from gateway.tasks.attribution import compute_correlation_task
from gateway.tenancy import require_business_access, require_business_write_access
from shared.models.core import AttributionCorrelation, User

router = APIRouter(tags=["attribution"])


class ComputeCorrelationRequest(BaseModel):
    business_id: uuid.UUID
    period_start: datetime
    period_end: datetime


class AttributionSummary(BaseModel):
    business_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    correlation_score: float | None
    signal_completeness_pct: float | None
    computed_at: datetime

    model_config = {"from_attributes": True}


@router.get("/businesses/{business_id}/attribution/summary", response_model=AttributionSummary)
async def attribution_summary(
    business_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttributionCorrelation:
    await require_business_access(business_id, user, db)
    result = (
        await db.execute(
            select(AttributionCorrelation)
            .where(AttributionCorrelation.business_id == business_id)
            .order_by(AttributionCorrelation.computed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if result is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No attribution correlation computed yet -- call compute-correlation first",
        )
    return result


@router.post("/attribution/compute-correlation", status_code=status.HTTP_202_ACCEPTED)
async def trigger_compute_correlation(
    body: ComputeCorrelationRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    await require_business_write_access(body.business_id, user, db)
    compute_correlation_task.delay(
        str(body.business_id), body.period_start.isoformat(), body.period_end.isoformat()
    )
    return {"status": "queued"}
