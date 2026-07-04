"""
services/sync-engine/campaigns.py

Campaign send orchestration: pre-flight cost estimate -> credit-ledger
debit -> adapter.send_message per contact -> CampaignMessage row. Never
charges for a failed send — debits are refunded if the adapter call
raises.

Runs synchronously from the API route in this pass (see
gateway/api/v1/whatsapp.py) rather than queued via Celery — flagged, not
silent: EVENT_ARCHITECTURE.md's intent is for broadcast-scale sends to be
queued, but keeping this synchronous keeps it directly testable without
requiring a live Celery worker in CI. Queueing it is a follow-up once
broadcast volumes actually justify it.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from services.billing import credit_ledger
from services.billing.credit_ledger import InsufficientCreditError
from shared.models.core import Campaign, CampaignMessage, CreditType, WhatsAppContact

from .adapters.whatsapp.base import MessageCategory, OutboundMessage, WhatsAppBSPAdapter


class CampaignSendResult:
    def __init__(self) -> None:
        self.sent = 0
        self.failed = 0
        self.skipped_insufficient_credit = 0


async def send_campaign(
    db: AsyncSession,
    adapter: WhatsAppBSPAdapter,
    campaign: Campaign,
    contacts: list[WhatsAppContact],
) -> CampaignSendResult:
    result = CampaignSendResult()
    category = MessageCategory(campaign.category)

    for contact in contacts:
        cost = Decimal(str(adapter.estimate_cost_inr(category)))

        message_row = CampaignMessage(
            campaign_id=campaign.id,
            contact_id=contact.id,
            status="pending",
        )
        db.add(message_row)
        await db.flush()

        if cost > 0:
            try:
                await credit_ledger.debit(
                    db,
                    campaign.business_id,
                    CreditType.whatsapp,
                    cost,
                    reference_type="wa_message",
                    reference_id=message_row.id,
                )
            except InsufficientCreditError:
                message_row.status = "skipped_insufficient_credit"
                result.skipped_insufficient_credit += 1
                await db.commit()
                continue

        outbound = OutboundMessage(
            business_id=str(campaign.business_id),
            to_phone_e164=contact.phone_e164,
            template_name=campaign.template_name,
            category=category,
            variables={},
            campaign_ref=str(campaign.id),
        )

        try:
            send_result = await adapter.send_message(outbound)
        except Exception:
            # Intentionally broad: adapters raise BSP-specific exception
            # types (e.g. GallaboxSendError) that this BSP-agnostic
            # orchestration code must not depend on, per base.py's
            # abstraction contract. Any failure means: never charge for a
            # send that didn't happen.
            if cost > 0:
                await credit_ledger.credit(
                    db,
                    campaign.business_id,
                    CreditType.whatsapp,
                    cost,
                    reference_type="wa_send_failed_refund",
                    reference_id=message_row.id,
                )
            message_row.status = "failed"
            result.failed += 1
            await db.commit()
            continue

        message_row.status = send_result.status.value
        message_row.provider_message_id = send_result.provider_message_id
        message_row.cost_inr = cost
        message_row.sent_at = send_result.sent_at
        result.sent += 1
        await db.commit()

    return result
