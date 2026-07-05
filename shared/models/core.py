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
    BigInteger, Boolean, DateTime, ForeignKey, Identity, Numeric, String, Text,
    Enum as SAEnum, Index, UniqueConstraint, func,
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
        Index("ix_businesses_agency_id", "agency_id"),
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
    # OAuth scaffold (see shared/secrets/vault_client.py's store()/resolve()
    # multi-key signature) -- populated once the real GBP/Meta token
    # exchange is wired up, both nullable until then.
    refresh_token_ref: Mapped[str | None] = mapped_column(String)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[list[str] | None] = mapped_column(JSONB)
    sync_status: Mapped[SyncStatus] = mapped_column(SAEnum(SyncStatus), default=SyncStatus.healthy)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # One connection per business+platform -- the OAuth callback
        # upserts rather than accumulating duplicate rows. No duplicates
        # existed when this was added (checked directly against the live
        # DB before writing the migration).
        UniqueConstraint("business_id", "platform", name="uq_platform_connections_business_platform"),
    )


class OAuthState(Base):
    """
    CSRF nonce for the OAuth authorize/callback handshake (gateway/api/v1/
    oauth.py). Short-lived (see OAUTH_STATE_TTL there) and single-use --
    used_at is set the moment the callback validates it, so a replayed
    callback with the same state is rejected on the second attempt.
    """
    __tablename__ = "oauth_states"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    platform: Mapped[PlatformName] = mapped_column(SAEnum(PlatformName), nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_oauth_states_business_id", "business_id"),
    )


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

    __table_args__ = (
        Index("ix_reviews_business_id", "business_id"),
    )


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

    `seq` (not `created_at`/`id`) is the authoritative "most recent entry"
    ordering: Postgres' `now()` returns the SAME value for every statement
    within one transaction, and `id` is a random UUID with no relationship
    to insertion order — a caught-in-testing bug where crediting the same
    business multiple times inside one transaction picked the wrong "latest"
    balance. `seq` is a real Postgres IDENTITY column, monotonic regardless
    of transaction timing.
    """
    __tablename__ = "credit_ledger"

    id: Mapped[uuid.UUID] = uuid_pk()
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False, unique=True)
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


class UserRole(str, enum.Enum):
    smb_owner = "smb_owner"
    agency_admin = "agency_admin"
    agency_viewer = "agency_viewer"


class User(Base):
    """
    PRESENCE's own login identity — distinct from platform-connection auth
    (GBP/Meta/WhatsApp OAuth), which lives on PlatformConnection instead.
    Exactly one of business_id/agency_id is expected to be set depending on
    role (smb_owner -> business_id, agency_admin/viewer -> agency_id).
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id"))
    agency_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agencies.id"))
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_users_business_id", "business_id"),
        Index("ix_users_agency_id", "agency_id"),
    )


class RefreshToken(Base):
    """Lets a refresh token be revoked server-side without a JWT blocklist."""
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WhatsAppContact(Base):
    """
    Customer module, minimal scope per CLAUDE.md: no consumer account/login
    system — just the WhatsApp contact list for campaign targeting.
    """
    __tablename__ = "whatsapp_contacts"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    phone_e164: Mapped[str] = mapped_column(String, nullable=False)
    opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[dict | None] = mapped_column(JSONB)
    # Tracks the WhatsApp 24hr free service window locally (from inbound
    # webhooks) rather than round-tripping to the BSP on every send
    # decision — see gallabox.py's get_conversation_status.
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("business_id", "phone_e164", name="uq_whatsapp_contact_business_phone"),
    )


class Campaign(Base):
    """
    category mirrors adapters.whatsapp.base.MessageCategory.value but is
    stored as a plain string here (not the services-layer enum) so
    shared/models never imports from services/*, per the clean-separation
    rule in CODING_STANDARDS.md.
    """
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    template_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_campaigns_business_id", "business_id"),
    )


class CampaignMessage(Base):
    __tablename__ = "campaign_messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("whatsapp_contacts.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="queued")
    provider_message_id: Mapped[str | None] = mapped_column(String)
    cost_inr: Mapped[float | None] = mapped_column(Numeric)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_campaign_messages_campaign", "campaign_id"),
    )


class NotificationEntry(Base):
    """In-app + email only for v1 — SMS/push deferred, per 06_MODULES/NOTIFICATIONS.md."""
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id"))
    agency_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agencies.id"))
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    channel: Mapped[str] = mapped_column(String, nullable=False)  # in_app|email
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_notifications_business_created", "business_id", "created_at"),
    )


class Subscription(Base):
    """
    Billing scope is subscription + credit recharge ONLY — embedded/
    commission payment collection is explicitly deferred, per
    06_MODULES/PAYMENTS.md.
    """
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    razorpay_subscription_id: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="created")
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_subscriptions_business_id", "business_id"),
    )


class ScheduledPost(Base):
    """Social module, narrow scope: read + basic scheduled posting only, no ads management."""
    __tablename__ = "scheduled_posts"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)  # meta|instagram
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_url: Mapped[str | None] = mapped_column(String)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_scheduled_posts_business_scheduled", "business_id", "scheduled_at"),
    )
