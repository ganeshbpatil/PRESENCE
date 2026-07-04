"""
gateway/tasks/attribution.py

Async Celery task wrapping the attribution engine's correlation compute —
EVENT_ARCHITECTURE.md requires this run async, never computed
synchronously in the request path. Celery's worker model is sync, so the
task wraps an asyncio.run() around the async DB/compute call (gateway/db.py
has no sync engine — this is the standard bridge pattern rather than
standing up a second, sync-only engine just for Celery).

Imports from services.attribution-engine.* via importlib for the same
reason documented in whatsapp.py/reviews.py: the hyphen in the directory
name (matching 06_MODULES/ANALYTICS.md's exact path) isn't valid literal
dotted-import syntax.
"""
from __future__ import annotations

import asyncio
import importlib
import uuid
from datetime import datetime

from gateway.celery_app import app
from gateway.db import async_session_factory

_correlation_mod = importlib.import_module("services.attribution-engine.correlation")
compute_correlation = _correlation_mod.compute_correlation


async def _run(business_id: str, period_start: str, period_end: str) -> None:
    async with async_session_factory() as db:
        await compute_correlation(
            db,
            uuid.UUID(business_id),
            datetime.fromisoformat(period_start),
            datetime.fromisoformat(period_end),
        )
        await db.commit()


@app.task(name="attribution.compute_correlation")
def compute_correlation_task(business_id: str, period_start: str, period_end: str) -> None:
    asyncio.run(_run(business_id, period_start, period_end))
