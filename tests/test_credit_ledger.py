"""
High-rigor tests for services/billing/credit_ledger.py, per
TESTING_STRATEGY.md ("attribution engine + billing/credit-ledger: high
rigor from day one... a silent bug here costs a customer relationship or a
compliance incident"). Runs against real Postgres — this module's whole
point is enforcing an invariant at the database layer, so a mocked test
would prove nothing.
"""
import uuid
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select

from gateway.db import async_session_factory
from services.billing.credit_ledger import InsufficientCreditError, credit, debit, get_balance
from shared.models.core import (
    Business,
    BusinessCategory,
    BusinessTier,
    CreditLedgerEntry,
    CreditType,
)


async def _make_business() -> uuid.UUID:
    async with async_session_factory() as db:
        business = Business(
            name=f"Ledger Test {uuid.uuid4()}",
            category=BusinessCategory.salon_spa_gym,
            tier=BusinessTier.starter,
        )
        db.add(business)
        await db.commit()
        await db.refresh(business)
        return business.id


@pytest.mark.asyncio
async def test_balance_starts_at_zero():
    business_id = await _make_business()
    async with async_session_factory() as db:
        assert await get_balance(db, business_id, CreditType.ai) == Decimal("0")


@pytest.mark.asyncio
async def test_credit_then_debit_computes_correct_balance():
    business_id = await _make_business()
    async with async_session_factory() as db:
        await credit(db, business_id, CreditType.whatsapp, Decimal("100.00"))
        await db.commit()

    async with async_session_factory() as db:
        entry = await debit(db, business_id, CreditType.whatsapp, Decimal("30.50"))
        await db.commit()
        assert entry.balance_after == Decimal("69.50")

    async with async_session_factory() as db:
        assert await get_balance(db, business_id, CreditType.whatsapp) == Decimal("69.50")


@pytest.mark.asyncio
async def test_debit_beyond_balance_raises_and_writes_no_row():
    business_id = await _make_business()
    async with async_session_factory() as db:
        await credit(db, business_id, CreditType.ai, Decimal("10.00"))
        await db.commit()

    async with async_session_factory() as db:
        with pytest.raises(InsufficientCreditError):
            await debit(db, business_id, CreditType.ai, Decimal("10.01"))
        await db.rollback()

    async with async_session_factory() as db:
        assert await get_balance(db, business_id, CreditType.ai) == Decimal("10.00")
        count = (
            await db.execute(
                select(CreditLedgerEntry).where(CreditLedgerEntry.business_id == business_id)
            )
        ).scalars().all()
        assert len(count) == 1  # only the original credit — failed debit wrote nothing


@pytest.mark.asyncio
async def test_ledger_is_append_only_never_updates_existing_rows():
    """The hard rule from CLAUDE.md principle #5: every credit/debit call
    must INSERT, never touch a prior row's balance_after."""
    business_id = await _make_business()
    async with async_session_factory() as db:
        first = await credit(db, business_id, CreditType.ai, Decimal("5.00"))
        await db.commit()
        first_id, first_balance = first.id, first.balance_after

    async with async_session_factory() as db:
        await credit(db, business_id, CreditType.ai, Decimal("5.00"))
        await db.commit()

    async with async_session_factory() as db:
        original = (
            await db.execute(select(CreditLedgerEntry).where(CreditLedgerEntry.id == first_id))
        ).scalar_one()
        assert original.balance_after == first_balance  # untouched by the later credit


@pytest.mark.asyncio
async def test_concurrent_debits_never_overdraw():
    """Property: N concurrent debits against a fixed starting balance must
    never let the balance go negative, and the final balance must equal
    (starting balance - sum of amounts that actually succeeded)."""
    import asyncio

    business_id = await _make_business()
    starting_balance = Decimal("50.00")
    async with async_session_factory() as db:
        await credit(db, business_id, CreditType.whatsapp, starting_balance)
        await db.commit()

    amount = Decimal("10.00")
    attempts = 10  # 10 x 10.00 against a 50.00 balance -> exactly 5 can succeed

    async def _attempt() -> bool:
        async with async_session_factory() as db:
            try:
                await debit(db, business_id, CreditType.whatsapp, amount)
                await db.commit()
                return True
            except InsufficientCreditError:
                await db.rollback()
                return False

    results = await asyncio.gather(*[_attempt() for _ in range(attempts)])
    succeeded = sum(results)

    async with async_session_factory() as db:
        final_balance = await get_balance(db, business_id, CreditType.whatsapp)

    assert final_balance >= Decimal("0")
    assert final_balance == starting_balance - (amount * succeeded)
    assert succeeded == 5


@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    deltas=st.lists(
        st.decimals(
            min_value=Decimal("0.01"), max_value=Decimal("1000.00"), places=2, allow_nan=False
        ),
        min_size=1,
        max_size=8,
    )
)
@pytest.mark.asyncio
async def test_property_balance_equals_sum_of_credits(deltas: list[Decimal]):
    """Property-based: crediting a fresh business N times must always leave
    balance_after equal to the running sum, regardless of amounts/order."""
    business_id = await _make_business()
    running_total = Decimal("0")
    async with async_session_factory() as db:
        for delta in deltas:
            entry = await credit(db, business_id, CreditType.ai, delta)
            running_total += delta
            assert entry.balance_after == running_total
        await db.commit()
