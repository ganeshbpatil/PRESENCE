"""
services/attribution-engine/correlation.py

v0 proxy-signal correlation ONLY (06_MODULES/ANALYTICS.md) — NOT full
multi-touch attribution modeling, which is explicitly deferred to Year 2+.
Correlates WhatsApp-campaign signals to proxy "customer interest" outcome
signals (direction_request, call) within a lag window, per business per
period.

`correlation_score` here means "the fraction of outcome signals that
followed a campaign signal within the lag window" — an attribution PROXY,
not a statistical Pearson correlation. The name matches the docs'
"correlation" terminology, but the math is intentionally simple and
auditable (v0 scope), not a black-box statistical model — a wrong number
here silently destroys product credibility (TESTING_STRATEGY.md), so
simple-and-checkable beats sophisticated-and-opaque.

Isolated from sync-engine per CLAUDE.md principle #3 — no shared DB
tables/models with sync-engine's own logic, only reads AttributionSignal /
writes AttributionCorrelation, both already-isolated tables.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.core import AttributionCorrelation, AttributionSignal

_OUTCOME_SIGNAL_TYPES = ("direction_request", "call")
_CAMPAIGN_SIGNAL_TYPES = ("whatsapp_click",)
_DEFAULT_LAG_WINDOW_DAYS = 7


async def compute_correlation(
    db: AsyncSession,
    business_id: uuid.UUID,
    period_start: datetime,
    period_end: datetime,
    lag_window_days: int = _DEFAULT_LAG_WINDOW_DAYS,
) -> AttributionCorrelation:
    if period_end <= period_start:
        raise ValueError("period_end must be after period_start")

    signals = list(
        (
            await db.execute(
                select(AttributionSignal).where(
                    AttributionSignal.business_id == business_id,
                    AttributionSignal.occurred_at >= period_start,
                    AttributionSignal.occurred_at < period_end,
                )
            )
        ).scalars()
    )

    campaign_times = sorted(
        s.occurred_at for s in signals if s.signal_type in _CAMPAIGN_SIGNAL_TYPES
    )
    outcome_signals = [s for s in signals if s.signal_type in _OUTCOME_SIGNAL_TYPES]

    lag = timedelta(days=lag_window_days)
    attributed = 0
    for outcome in outcome_signals:
        # Any campaign signal in [outcome_time - lag, outcome_time] counts
        # as a plausible driver — proxy correlation, not causal proof.
        if any(
            outcome.occurred_at - lag <= campaign_time <= outcome.occurred_at
            for campaign_time in campaign_times
        ):
            attributed += 1

    correlation_score = (
        Decimal(attributed) / Decimal(len(outcome_signals))
        if outcome_signals
        else Decimal("0")
    )

    days_in_period = max((period_end - period_start).days, 1)
    days_with_signal = len({s.occurred_at.date() for s in signals})
    signal_completeness_pct = min(
        (Decimal(days_with_signal) / Decimal(days_in_period)) * Decimal(100),
        Decimal("100"),
    )

    correlation = AttributionCorrelation(
        business_id=business_id,
        period_start=period_start,
        period_end=period_end,
        correlation_score=correlation_score,
        signal_completeness_pct=signal_completeness_pct,
    )
    db.add(correlation)
    await db.flush()
    return correlation
