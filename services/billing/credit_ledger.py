"""
services/billing/credit_ledger.py

Single place enforcing the append-only invariant on credit_ledger (see
shared/models/core.py:CreditLedgerEntry and CLAUDE.md principle #5) — never
UPDATE balance_after on an existing row, always INSERT a new one computed
from the prior balance. Concurrency safety comes from a Postgres
transaction-scoped advisory lock keyed on (business_id, credit_type), not
row locking — there is no standalone "balance" row to lock, the balance is
derived from the latest ledger entry.

Reused by both WhatsApp campaign sends and AI orchestrator billing (and
recharge) — feature code must go through debit()/credit() here, never
insert a CreditLedgerEntry directly.
"""
from __future__ import annotations

import hashlib
import struct
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.core import CreditLedgerEntry, CreditType


class InsufficientCreditError(Exception):
    def __init__(
        self,
        business_id: uuid.UUID,
        credit_type: CreditType,
        balance: Decimal,
        requested: Decimal,
    ):
        self.business_id = business_id
        self.credit_type = credit_type
        self.balance = balance
        self.requested = requested
        super().__init__(
            f"Insufficient {credit_type.value} credit for business {business_id}: "
            f"balance={balance}, requested={requested}"
        )


def _advisory_lock_key(business_id: uuid.UUID, credit_type: CreditType) -> int:
    """Stable signed-64-bit key for pg_advisory_xact_lock — derived in
    Python (not Postgres hashtext) to sidestep int4/int8 overload
    ambiguity."""
    raw = f"{business_id}:{credit_type.value}".encode()
    digest = hashlib.sha256(raw).digest()[:8]
    return struct.unpack(">q", digest)[0]


async def _lock(db: AsyncSession, business_id: uuid.UUID, credit_type: CreditType) -> None:
    # Released automatically at COMMIT/ROLLBACK — never needs an explicit
    # unlock, and is safe to acquire more than once per transaction.
    lock_key = _advisory_lock_key(business_id, credit_type)
    await db.execute(select(func.pg_advisory_xact_lock(lock_key)))


async def get_balance(
    db: AsyncSession, business_id: uuid.UUID, credit_type: CreditType
) -> Decimal:
    result = await db.execute(
        select(CreditLedgerEntry.balance_after)
        .where(
            CreditLedgerEntry.business_id == business_id,
            CreditLedgerEntry.credit_type == credit_type,
        )
        # seq, not created_at (see CreditLedgerEntry docstring): now() ties
        # within a transaction, but seq is a real monotonic IDENTITY column.
        .order_by(CreditLedgerEntry.seq.desc())
        .limit(1)
    )
    balance = result.scalar_one_or_none()
    return Decimal(balance) if balance is not None else Decimal("0")


async def _append(
    db: AsyncSession,
    business_id: uuid.UUID,
    credit_type: CreditType,
    delta: Decimal,
    balance_after: Decimal,
    reference_type: str | None,
    reference_id: uuid.UUID | None,
) -> CreditLedgerEntry:
    entry = CreditLedgerEntry(
        business_id=business_id,
        credit_type=credit_type,
        delta=delta,
        reference_type=reference_type,
        reference_id=reference_id,
        balance_after=balance_after,
    )
    db.add(entry)
    await db.flush()
    return entry


async def credit(
    db: AsyncSession,
    business_id: uuid.UUID,
    credit_type: CreditType,
    amount: Decimal,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
) -> CreditLedgerEntry:
    if amount <= 0:
        raise ValueError("credit amount must be positive")

    await _lock(db, business_id, credit_type)
    balance = await get_balance(db, business_id, credit_type)
    return await _append(
        db, business_id, credit_type, amount, balance + amount, reference_type, reference_id
    )


async def debit(
    db: AsyncSession,
    business_id: uuid.UUID,
    credit_type: CreditType,
    amount: Decimal,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
) -> CreditLedgerEntry:
    """Raises InsufficientCreditError without writing a row if the debit
    would take the balance negative — callers (e.g. WhatsApp send
    orchestration) must check this pre-flight, per the WhatsApp module's
    cost-estimate-before-send requirement."""
    if amount <= 0:
        raise ValueError("debit amount must be positive")

    await _lock(db, business_id, credit_type)
    balance = await get_balance(db, business_id, credit_type)
    if balance < amount:
        raise InsufficientCreditError(business_id, credit_type, balance, amount)

    return await _append(
        db, business_id, credit_type, -amount, balance - amount, reference_type, reference_id
    )
