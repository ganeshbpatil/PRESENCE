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
from gateway.tenancy import require_business_access, require_business_write_access
from services.billing import credit_ledger
from services.billing.razorpay_client import (
    RazorpayClient,
    RazorpayError,
    verify_webhook_signature,
)
from shared.models.core import CreditLedgerEntry, CreditType, Subscription, User

# Namespace for deriving a stable UUID from a Razorpay payment ID (not a
# secret -- just gives recharge_credit() a reference_id to key idempotency
# on, since CreditLedgerEntry.reference_id is UUID-typed and Razorpay's IDs
# aren't UUIDs).
_RAZORPAY_PAYMENT_REFERENCE_NAMESPACE = uuid.UUID("6f5a1d3e-6e7c-4a3a-8b0e-0f6a1f7d9c2a")

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
    # A real captured Razorpay payment ID (e.g. from a Payment Link or
    # Checkout flow) -- NOT a client-supplied amount. recharge_credit fetches
    # the payment from Razorpay and credits exactly what Razorpay confirms
    # was captured; nothing about the credited amount is caller-controlled.
    razorpay_payment_id: str


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
    await require_business_write_access(body.business_id, user, db)
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
    await require_business_write_access(business_id, user, db)
    settings = get_settings()

    if not (settings.razorpay_key_id and settings.razorpay_key_secret):
        # Phase 0 placeholder .env, no live Razorpay account configured yet
        # -- same "untestable until secrets configured" precedent as
        # create_subscription above. Refuse rather than silently accept an
        # unverifiable recharge.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Razorpay is not configured"
        )

    client = RazorpayClient(settings.razorpay_key_id, settings.razorpay_key_secret)
    try:
        payment = await client.fetch_payment(body.razorpay_payment_id)
    except RazorpayError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    if payment.get("status") != "captured":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Razorpay payment {body.razorpay_payment_id} is not captured "
            f"(status={payment.get('status')!r})",
        )
    if payment.get("currency") != "INR":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Only INR payments are supported"
        )

    # Razorpay reports amount in paise; the ledger is rupee-denominated.
    amount = Decimal(payment["amount"]) / Decimal(100)

    reference_id = uuid.uuid5(
        _RAZORPAY_PAYMENT_REFERENCE_NAMESPACE, body.razorpay_payment_id
    )
    already_credited = (
        await db.execute(
            select(CreditLedgerEntry).where(
                CreditLedgerEntry.business_id == business_id,
                CreditLedgerEntry.reference_type == "razorpay_payment",
                CreditLedgerEntry.reference_id == reference_id,
            )
        )
    ).scalar_one_or_none()
    if already_credited is not None:
        # Idempotent replay -- same payment ID submitted twice (e.g. a
        # retried frontend request) must not double-credit.
        return BalanceResponse(
            business_id=business_id,
            credit_type=body.credit_type,
            balance=already_credited.balance_after,
        )

    entry = await credit_ledger.credit(
        db,
        business_id,
        body.credit_type,
        amount,
        reference_type="razorpay_payment",
        reference_id=reference_id,
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
