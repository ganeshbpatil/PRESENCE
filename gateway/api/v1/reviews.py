"""
gateway/api/v1/reviews.py

Reviews + AI-drafted responses. Draft-then-approve only per
ACCEPTANCE_CRITERIA.md — draft-response never sends anything, send-response
is a distinct, explicit human action.

Imports from services.ai-orchestrator.* via importlib for the same reason
documented in whatsapp.py: "ai-orchestrator" has a hyphen, valid as an
import path string but not as literal dotted-import syntax.
"""
from __future__ import annotations

import importlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.config import Settings, get_settings
from gateway.db import get_db
from gateway.security import get_current_user
from gateway.tenancy import require_business_access, require_business_write_access
from services.billing import credit_ledger
from services.billing.credit_ledger import InsufficientCreditError
from services.notifications.notifier import notify
from shared.events import EventType
from shared.models.core import Business, CreditType, PlatformName, Review, User

_factory_mod = importlib.import_module("services.ai-orchestrator.factory")
_router_mod = importlib.import_module("services.ai-orchestrator.router")
get_orchestrator = _factory_mod.get_orchestrator
AIRequest = _router_mod.AIRequest
AIProviderError = _router_mod.AIProviderError

router = APIRouter(tags=["reviews"])

# Flat USD-per-call estimate for AI credit debiting until a real per-model
# token-rate table exists (same open item as the WhatsApp adapter's
# estimate_cost_inr — see its TODO). Kept as a named constant, not scattered
# magic numbers.
_AI_CALL_CREDIT_COST = Decimal("0.02")


class ReviewCreate(BaseModel):
    """Stand-in for the GBP/Meta sync job, which isn't built in this pass
    (no live platform credentials) — lets the review -> draft -> send flow
    be exercised end-to-end without it."""

    platform: PlatformName
    external_review_id: str | None = None
    rating: int | None = None
    text: str | None = None


class ReviewResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    platform: PlatformName
    rating: int | None
    text: str | None
    ai_drafted_response: str | None
    response_sent_at: datetime | None

    model_config = {"from_attributes": True}


class DraftResponseResult(BaseModel):
    review: ReviewResponse
    cache_hit: bool


async def _get_review_or_404(review_id: uuid.UUID, db: AsyncSession) -> Review:
    review = (await db.execute(select(Review).where(Review.id == review_id))).scalar_one_or_none()
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found")
    return review


@router.post(
    "/businesses/{business_id}/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_review(
    business_id: uuid.UUID,
    body: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Review:
    await require_business_write_access(business_id, user, db)
    review = Review(
        business_id=business_id,
        platform=body.platform,
        external_review_id=body.external_review_id,
        rating=body.rating,
        text=body.text,
    )
    db.add(review)
    await db.flush()

    await notify(
        db,
        EventType.REVIEW_RECEIVED,
        {"review_id": str(review.id), "rating": review.rating},
        redis_url=settings.redis_url,
        business_id=business_id,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_password=settings.smtp_password,
        smtp_from_email=settings.smtp_from_email,
    )

    await db.commit()
    await db.refresh(review)
    return review


@router.get("/businesses/{business_id}/reviews", response_model=list[ReviewResponse])
async def list_reviews(
    business_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Review]:
    await require_business_access(business_id, user, db)
    result = await db.execute(select(Review).where(Review.business_id == business_id))
    return list(result.scalars().all())


@router.post("/reviews/{review_id}/draft-response", response_model=DraftResponseResult)
async def draft_response(
    review_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> DraftResponseResult:
    review = await _get_review_or_404(review_id, db)
    await require_business_write_access(review.business_id, user, db)
    business = (
        await db.execute(select(Business).where(Business.id == review.business_id))
    ).scalar_one()

    try:
        await credit_ledger.debit(
            db,
            business.id,
            CreditType.ai,
            _AI_CALL_CREDIT_COST,
            reference_type="ai_call",
            reference_id=review.id,
        )
    except InsufficientCreditError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, str(exc)) from exc

    orchestrator = get_orchestrator(
        redis_url=settings.redis_url,
        default_provider=settings.ai_default_provider,
        cache_ttl_seconds=settings.ai_cache_ttl_seconds,
        openrouter_api_key=settings.openrouter_api_key,
        anthropic_api_key=settings.anthropic_api_key,
    )

    try:
        result = await orchestrator.complete(
            AIRequest(
                prompt_template_id="review_response_draft_v1",
                variables={
                    "business_name": business.name,
                    "business_category": business.category.value,
                    "rating": review.rating,
                    "review_text": review.text or "(no text provided)",
                },
                business_id=str(business.id),
            )
        )
    except AIProviderError as exc:
        # Refund the debit -- never charge for a draft that didn't happen.
        # Expected in this environment: OPENROUTER_API_KEY/ANTHROPIC_API_KEY
        # are placeholders in .env, so this path is real but untestable
        # end-to-end here (same precedent as PR #1's docker-build gap).
        await credit_ledger.credit(
            db,
            business.id,
            CreditType.ai,
            _AI_CALL_CREDIT_COST,
            reference_type="ai_call_failed_refund",
            reference_id=review.id,
        )
        await db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    review.ai_drafted_response = result.text
    await db.commit()
    await db.refresh(review)
    return DraftResponseResult(review=review, cache_hit=result.cache_hit)


@router.post("/reviews/{review_id}/send-response", response_model=ReviewResponse)
async def send_response(
    review_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Review:
    review = await _get_review_or_404(review_id, db)
    await require_business_write_access(review.business_id, user, db)

    if review.ai_drafted_response is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No drafted response to send -- call draft-response first",
        )
    if review.response_sent_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Response already sent")

    # This endpoint IS the explicit human-approval action per
    # ACCEPTANCE_CRITERIA.md's draft-then-approve requirement -- there is
    # no auto-send path anywhere in this codebase.
    review.response_sent_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(review)
    return review
