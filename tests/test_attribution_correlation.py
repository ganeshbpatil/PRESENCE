"""
High-rigor tests for services/attribution-engine/correlation.py, per
TESTING_STRATEGY.md's carve-out ("attribution engine... high rigor from
day one... a silent bug here silently destroys product credibility").
Runs against real Postgres for the same reason test_credit_ledger.py does.
"""
import importlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from gateway.db import async_session_factory
from shared.models.core import (
    AttributionSignal,
    Business,
    BusinessCategory,
    BusinessTier,
)

_correlation_mod = importlib.import_module("services.attribution-engine.correlation")
compute_correlation = _correlation_mod.compute_correlation

_PERIOD_START = datetime(2026, 1, 1, tzinfo=UTC)
_PERIOD_END = datetime(2026, 1, 15, tzinfo=UTC)  # 14-day period


async def _make_business() -> uuid.UUID:
    async with async_session_factory() as db:
        business = Business(
            name=f"Attribution Test {uuid.uuid4()}",
            category=BusinessCategory.salon_spa_gym,
            tier=BusinessTier.starter,
        )
        db.add(business)
        await db.commit()
        await db.refresh(business)
        return business.id


async def _add_signal(business_id: uuid.UUID, signal_type: str, occurred_at: datetime) -> None:
    async with async_session_factory() as db:
        db.add(
            AttributionSignal(
                business_id=business_id,
                signal_type=signal_type,
                occurred_at=occurred_at,
                lag_window_days=7,
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_period_end_before_start_raises():
    business_id = await _make_business()
    async with async_session_factory() as db:
        with pytest.raises(ValueError):
            await compute_correlation(db, business_id, _PERIOD_END, _PERIOD_START)


@pytest.mark.asyncio
async def test_no_outcome_signals_yields_zero_correlation():
    business_id = await _make_business()
    await _add_signal(business_id, "whatsapp_click", _PERIOD_START + timedelta(days=1))

    async with async_session_factory() as db:
        result = await compute_correlation(db, business_id, _PERIOD_START, _PERIOD_END)
        await db.commit()

    assert result.correlation_score == Decimal("0")


@pytest.mark.asyncio
async def test_every_outcome_signal_preceded_by_campaign_yields_full_correlation():
    business_id = await _make_business()
    campaign_day = _PERIOD_START + timedelta(days=2)
    await _add_signal(business_id, "whatsapp_click", campaign_day)
    # Both within the 7-day lag window after the campaign signal.
    await _add_signal(business_id, "direction_request", campaign_day + timedelta(days=1))
    await _add_signal(business_id, "call", campaign_day + timedelta(days=3))

    async with async_session_factory() as db:
        result = await compute_correlation(db, business_id, _PERIOD_START, _PERIOD_END)
        await db.commit()

    assert result.correlation_score == Decimal("1")


@pytest.mark.asyncio
async def test_outcome_signal_outside_lag_window_is_not_attributed():
    business_id = await _make_business()
    campaign_day = _PERIOD_START + timedelta(days=1)
    await _add_signal(business_id, "whatsapp_click", campaign_day)
    # 8 days after the campaign signal -- outside the default 7-day lag.
    await _add_signal(business_id, "direction_request", campaign_day + timedelta(days=8))

    async with async_session_factory() as db:
        result = await compute_correlation(db, business_id, _PERIOD_START, _PERIOD_END)
        await db.commit()

    assert result.correlation_score == Decimal("0")


@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    signals=st.lists(
        st.tuples(
            st.sampled_from(["whatsapp_click", "direction_request", "call"]),
            st.integers(min_value=0, max_value=13),  # day offset within the 14-day period
        ),
        min_size=0,
        max_size=20,
    )
)
@pytest.mark.asyncio
async def test_property_scores_always_stay_within_valid_bounds(
    signals: list[tuple[str, int]],
):
    """Property: regardless of how many/which signals occur, correlation_score
    must stay in [0, 1] and signal_completeness_pct must stay in [0, 100] --
    a bug that lets either escape its bound would silently produce a
    nonsensical number on a customer-facing dashboard."""
    business_id = await _make_business()
    for signal_type, day_offset in signals:
        await _add_signal(business_id, signal_type, _PERIOD_START + timedelta(days=day_offset))

    async with async_session_factory() as db:
        result = await compute_correlation(db, business_id, _PERIOD_START, _PERIOD_END)
        await db.commit()

    assert Decimal("0") <= result.correlation_score <= Decimal("1")
    assert Decimal("0") <= result.signal_completeness_pct <= Decimal("100")
