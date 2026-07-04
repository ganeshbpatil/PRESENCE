"""
gateway/api/v1/whatsapp.py

Campaigns + contacts + the public Gallabox webhook. Highest-priority
module per 06_MODULES/WHATSAPP.md.

Imports from services.sync-engine.* via importlib rather than a literal
`from services.sync-engine import ...` statement: "sync-engine" has a
hyphen, which is a valid directory/module name at import time (Python
resolves dotted module paths as strings) but not valid literal dotted-
import syntax (the hyphen parses as a minus operator). The directory name
itself matches the path already used throughout docs/PRESENCE and PR #1's
existing adapters/whatsapp files, so renaming it was a bigger footprint
than working around it here.
"""
from __future__ import annotations

import importlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.config import Settings, get_settings
from gateway.db import get_db
from gateway.security import get_current_user
from gateway.tenancy import require_business_access
from services.notifications.notifier import notify
from shared.events import EventType
from shared.models.core import Campaign, CampaignMessage, User, WhatsAppContact

_campaigns_mod = importlib.import_module("services.sync-engine.campaigns")
_factory_mod = importlib.import_module("services.sync-engine.adapters.whatsapp.factory")
_base_mod = importlib.import_module("services.sync-engine.adapters.whatsapp.base")

send_campaign = _campaigns_mod.send_campaign
get_adapter = _factory_mod.get_adapter
MessageCategory = _base_mod.MessageCategory
SendResult = _base_mod.SendResult
DeliveryStatus = _base_mod.DeliveryStatus
GallaboxWebhookError = importlib.import_module(
    "services.sync-engine.adapters.whatsapp.gallabox"
).GallaboxWebhookError

router = APIRouter(tags=["whatsapp"])


class ContactCreate(BaseModel):
    business_id: uuid.UUID
    phone_e164: str
    opt_in: bool = True
    tags: dict | None = None


class ContactResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    phone_e164: str
    opt_in: bool
    tags: dict | None

    model_config = {"from_attributes": True}


class CampaignCreate(BaseModel):
    business_id: uuid.UUID
    name: str
    template_name: str
    category: MessageCategory
    contact_ids: list[uuid.UUID] | None = None  # None = all opted-in contacts


class CampaignResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    name: str
    template_name: str
    category: str
    status: str

    model_config = {"from_attributes": True}


class CampaignSendSummary(BaseModel):
    campaign: CampaignResponse
    sent: int
    failed: int
    skipped_insufficient_credit: int


@router.post("/contacts", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    body: ContactCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WhatsAppContact:
    await require_business_access(body.business_id, user, db)
    contact = WhatsAppContact(
        business_id=body.business_id,
        phone_e164=body.phone_e164,
        opt_in=body.opt_in,
        tags=body.tags,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.get("/businesses/{business_id}/contacts", response_model=list[ContactResponse])
async def list_contacts(
    business_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WhatsAppContact]:
    await require_business_access(business_id, user, db)
    result = await db.execute(
        select(WhatsAppContact).where(WhatsAppContact.business_id == business_id)
    )
    return list(result.scalars().all())


@router.post("/campaigns", response_model=CampaignSendSummary, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    body: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CampaignSendSummary:
    await require_business_access(body.business_id, user, db)

    campaign = Campaign(
        business_id=body.business_id,
        name=body.name,
        template_name=body.template_name,
        category=body.category.value,
        status="sending",
    )
    db.add(campaign)
    await db.flush()

    contact_query = select(WhatsAppContact).where(
        WhatsAppContact.business_id == body.business_id, WhatsAppContact.opt_in.is_(True)
    )
    if body.contact_ids:
        contact_query = contact_query.where(WhatsAppContact.id.in_(body.contact_ids))
    contacts = list((await db.execute(contact_query)).scalars().all())

    adapter = get_adapter(
        "gallabox",
        db,
        gallabox_api_key=settings.gallabox_api_key,
        gallabox_api_secret=settings.gallabox_api_secret,
        gallabox_webhook_secret=settings.gallabox_webhook_secret,
    )
    result = await send_campaign(db, adapter, campaign, contacts)

    campaign.status = "sent"
    await db.commit()
    await db.refresh(campaign)

    return CampaignSendSummary(
        campaign=campaign,
        sent=result.sent,
        failed=result.failed,
        skipped_insufficient_credit=result.skipped_insufficient_credit,
    )


@router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Campaign:
    campaign = (
        await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    ).scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    await require_business_access(campaign.business_id, user, db)
    return campaign


@router.post("/webhooks/whatsapp/gallabox", status_code=status.HTTP_200_OK)
async def gallabox_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    raw_body = await request.body()
    adapter = get_adapter(
        "gallabox",
        db,
        gallabox_api_key=settings.gallabox_api_key,
        gallabox_api_secret=settings.gallabox_api_secret,
        gallabox_webhook_secret=settings.gallabox_webhook_secret,
    )

    try:
        parsed = await adapter.parse_webhook(raw_body, dict(request.headers))
    except GallaboxWebhookError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    # SendResult -> a delivery-status update for a message we sent; update
    # the matching CampaignMessage row so campaign delivery stats stay live.
    # (InboundMessage -> a customer reply; already recorded onto
    # WhatsAppContact.last_inbound_at by the adapter itself.)
    if isinstance(parsed, SendResult):
        campaign_message = (
            await db.execute(
                select(CampaignMessage).where(
                    CampaignMessage.provider_message_id == parsed.provider_message_id
                )
            )
        ).scalar_one_or_none()
        if campaign_message is not None:
            campaign_message.status = parsed.status.value

            if parsed.status in (DeliveryStatus.DELIVERED, DeliveryStatus.FAILED):
                campaign = (
                    await db.execute(
                        select(Campaign).where(Campaign.id == campaign_message.campaign_id)
                    )
                ).scalar_one_or_none()
                if campaign is not None:
                    event_type = (
                        EventType.WHATSAPP_MESSAGE_DELIVERED
                        if parsed.status == DeliveryStatus.DELIVERED
                        else EventType.WHATSAPP_MESSAGE_FAILED
                    )
                    await notify(
                        db,
                        event_type,
                        {
                            "campaign_message_id": str(campaign_message.id),
                            "provider_message_id": parsed.provider_message_id,
                        },
                        redis_url=settings.redis_url,
                        business_id=campaign.business_id,
                        smtp_host=settings.smtp_host,
                        smtp_port=settings.smtp_port,
                        smtp_user=settings.smtp_user,
                        smtp_password=settings.smtp_password,
                        smtp_from_email=settings.smtp_from_email,
                    )

    await db.commit()
    return {"status": "ok"}
