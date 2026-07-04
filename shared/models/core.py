"""
shared/models/core.py

Canonical data models. This is the single source of truth for schema —
Alembic migrations are generated FROM these models, not hand-written
independently. If Claude Code (or anyone) needs a new field, add it here
first, then autogenerate the migration.

Design principles enforced here (see CLAUDE.md for rationale):
- Money as Numeric, never Float
- Timestamps TZ-aware, UTC
- Credit ledger is append-only (no balance UPDATE — see CreditLedgerEntry)
- churned_at is nullable-until-churned, feeds cohort_retention view
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Numeric, String, Text, Enum as SAEnum,
    Index, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    pass


def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class BusinessTier(str, enum.Enum):
    starter = "starter"
    growth = "growth"
    scale = "scale"
    agency = "agency"


class BusinessCategory(str, enum.Enum):
    # Kept narrow deliberately — v1 persona is salons/spas/gyms per the
    # build roadmap's Phase 1 recommendation. Others exist for pilot
    # flexibility but should not all be actively sold in parallel yet.
    salon_spa_gym = "salon_spa_gym"
    clinic_healthcare = "clinic_healthcare"
    fnb = "fnb"
    retail_fashion_jewellery = "retail_fashion_jewellery"


class PlatformName(str, enum.Enum):
    gbp = "gbp"
    meta = "meta"
    whatsapp = "whatsapp"


class SyncStatus(str, enum.Enum):
    healthy = "healthy"
    degraded = "degraded"
    broken = "broken"


class Agency(Base):
    __tablename__ = "agencies"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_white_label: Mapped[bool] = mapped_column(Boolean, default=False)
    branding_config: Mapped[dict | None] = mapped_column(JSONB)
    revenue_share_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    businesses: Mapped[list["Business"]] = relationship(back_populates="agency")


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = uuid_pk()
    agency_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agencies.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[BusinessCategory] = mapped_column(SAEnum(BusinessCategory), nullable=False)
    tier: Mapped[BusinessTier] = mapped_column(SAEnum(BusinessTier), nullable=False)
    subscription_status: Mapped[str | None] = mapped_column(String)
    pincode: Mapped[str | None] = mapped_column(String)
    area: Mapped[str | None] = mapped_column(String)  # maps to Pune area ranking
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    churned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    agency: Mapped[Agency | None] = relationship(back_populates="businesses")

    __table_args__ = (
        Index("ix_businesses_category_tier", "category", "tier"),
        Index("ix_businesses_churned_at", "churned_at"),
    )


class PlatformConnection(Base):
    """
    GBP/Meta/WhatsApp are SYNC SOURCES, never system of record.
    sync_status feeds the customer-facing platform-health dashboard
    (turns platform-dependency risk into a trust signal per CLAUDE.md
    principle #1).
    """
    __tablename__ = "platform_connections"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    platform: Mapped[PlatformName] = mapped_column(SAEnum(PlatformName), nullable=False)
    provider: Mapped[str | None] = mapped_column(String)  # BSP name if platform == whatsapp
    external_id: Mapped[str | None] = mapped_column(String)
    access_token_ref: Mapped[str | None] = mapped_column(String)  # vault reference, never raw token
    sync_status: Mapped[SyncStatus] = mapped_column(SAEnum(SyncStatus), default=SyncStatus.healthy)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Review(Base):
    """Canonical review data — OUR system of record, synced from platforms."""
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    platform: Mapped[PlatformName] = mapped_column(SAEnum(PlatformName), nullable=False)
    external_review_id: Mapped[str | None] = mapped_column(String)
    rating: Mapped[int | None] = mapped_column()
    text: Mapped[str | None] = mapped_column(Text)
    ai_drafted_response: Mapped[str | None] = mapped_column(Text)
    response_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AttributionSignal(Base):
    """
    Raw proxy signals — direction requests, calls, WhatsApp-campaign clicks.
    This table is the attribution engine's INPUT. Keep it append-only and
    fine-grained; aggregation happens in AttributionCorrelation, not here.
    """
    __tablename__ = "attribution_signals"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    signal_type: Mapped[str] = mapped_column(String, nullable=False)  # direction_request|call|whatsapp_click
    campaign_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    value: Mapped[float | None] = mapped_column(Numeric)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lag_window_days: Mapped[int | None] = mapped_column()

    __table_args__ = (
        Index("ix_attribution_signals_business_occurred", "business_id", "occurred_at"),
    )


class AttributionCorrelation(Base):
    """
    Computed correlation output — this is what the attribution dashboard
    (P0 screen per build roadmap) reads. signal_completeness_pct is a
    product-quality leading indicator, not a vanity metric — track it.
    """
    __tablename__ = "attribution_correlations"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    signal_completeness_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CreditType(str, enum.Enum):
    ai = "ai"
    whatsapp = "whatsapp"


class CreditLedgerEntry(Base):
    """
    APPEND-ONLY. Never UPDATE balance_after on an existing row — insert a
    new row with the delta and the resulting balance_after. This is a hard
    rule (concurrency safety + audit trail for a billing-adjacent table),
    not a style preference. See CLAUDE.md principle #5.
    """
    __tablename__ = "credit_ledger"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    credit_type: Mapped[CreditType] = mapped_column(SAEnum(CreditType), nullable=False)
    delta: Mapped[float] = mapped_column(Numeric, nullable=False)  # +recharge / -consumption
    reference_type: Mapped[str | None] = mapped_column(String)  # ai_call|wa_message|recharge
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    balance_after: Mapped[float] = mapped_column(Numeric, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_credit_ledger_business_created", "business_id", "created_at"),
    )
