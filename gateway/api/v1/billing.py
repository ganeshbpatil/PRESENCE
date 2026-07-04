"""
gateway/api/v1/billing.py

Payments scope is subscription billing + AI/WhatsApp credit recharge ONLY
(06_MODULES/PAYMENTS.md) — no embedded/commission payment collection.
No shared router prefix: this file covers three distinct path families
(/billing, /credit-ledger, /webhooks) per API_STANDARDS.md's representative
contract.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.config import get_settings
from gateway.db import get_db
from gateway.security import get_current_user
from gateway.tenancy import require_business_access
from services.billing import credit_ledger
from services.billing.razorpay_client import (
    RazorpayClient,
    RazorpayError,
    verify_webhook_signature,
)
from shared.models.core import CreditType, Subscription, User

router = APIRouter(tags=["billing"])


class SubscriptionCreate(BaseModel):
    business_id: uuid.UUID
    plan_id: str
    total_count: int = 12


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    razorpay_subscription_id: str | None
    status: str

    model_config = {"from_attributes": True}


class RechargeRequest(BaseModel):
    credit_type: CreditType
    amount: Decimal
    reference_type: str = "recharge"


class BalanceResponse(BaseModel):
    business_id: uuid.UUID
    credit_type: CreditType
    balance: Decimal


@router.post(
    "/billing/subscriptions",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription(
    body: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Subscription:
    await require_business_access(body.business_id, user, db)
    settings = get_settings()

    razorpay_subscription_id = None
    sub_status = "created"
    if settings.razorpay_key_id and settings.razorpay_key_secret:
        client = RazorpayClient(settings.razorpay_key_id, settings.razorpay_key_secret)
        try:
            rp_sub = await client.create_subscription(body.plan_id, body.total_count)
            razorpay_subscription_id = rp_sub.get("id")
            sub_status = rp_sub.get("status", sub_status)
        except RazorpayError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    # else: RAZORPAY_KEY_ID/SECRET not configured (Phase 0 placeholder
    # .env) — record the local Subscription row in "created" state without
    # a live Razorpay-side object; the CI_CD/README precedent for
    # "untestable until secrets configured" applies here too.

    subscription = Subscription(
        business_id=body.business_id,
        razorpay_subscription_id=razorpay_subscription_id,
        status=sub_status,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.post("/webhooks/razorpay", status_code=status.HTTP_200_OK)
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    settings = get_settings()
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not verify_webhook_signature(raw_body, signature, settings.razorpay_webhook_secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook signature")

    payload = await request.json()
    event = payload.get("event", "")
    entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    razorpay_subscription_id = entity.get("id")

    if razorpay_subscription_id:
        subscription = (
            await db.execute(
                select(Subscription).where(
                    Subscription.razorpay_subscription_id == razorpay_subscription_id
                )
            )
        ).scalar_one_or_none()
        if subscription is not None:
            if event == "subscription.charged":
                subscription.status = "active"
            elif event == "subscription.cancelled":
                subscription.status = "cancelled"
            elif event == "subscription.halted":
                subscription.status = "halted"
            await db.commit()

    return {"status": "ok"}


@router.post("/credit-ledger/{business_id}/recharge", response_model=BalanceResponse)
async def recharge_credit(
    business_id: uuid.UUID,
    body: RechargeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BalanceResponse:
    # NOTE: this trusts the caller-supplied amount. A production version
    # should instead be driven by a verified Razorpay payment-capture
    # webhook (mirroring razorpay_webhook above), not a client-authored
    # amount — flagging rather than silently shipping this as bulletproof,
    # since there's no live Razorpay flow to verify against in this pass.
    await require_business_access(business_id, user, db)
    entry = await credit_ledger.credit(
        db, business_id, body.credit_type, body.amount, reference_type=body.reference_type
    )
    await db.commit()
    return BalanceResponse(
        business_id=business_id, credit_type=body.credit_type, balance=entry.balance_after
    )


@router.get("/credit-ledger/{business_id}/balance", response_model=list[BalanceResponse])
async def get_balances(
    business_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[BalanceResponse]:
    await require_business_access(business_id, user, db)
    return [
        BalanceResponse(
            business_id=business_id,
            credit_type=credit_type,
            balance=await credit_ledger.get_balance(db, business_id, credit_type),
        )
        for credit_type in CreditType
    ]
