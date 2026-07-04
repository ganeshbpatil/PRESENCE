"""
gateway/tasks/sync.py

Publishes ScheduledPost rows whose scheduled_at has passed. Wired into
Celery beat (see celery_app.py's beat_schedule) to run periodically —
actual posting is async/queued, never triggered synchronously from a
request, per EVENT_ARCHITECTURE.md.
"""
from __future__ import annotations

import asyncio
import importlib
from datetime import UTC, datetime

from sqlalchemy import select

from gateway.celery_app import app
from gateway.db import async_session_factory
from shared.models.core import PlatformConnection, PlatformName, ScheduledPost

_meta_mod = importlib.import_module("services.sync-engine.adapters.social.meta")
MetaAdapter = _meta_mod.MetaAdapter
MetaAdapterError = _meta_mod.MetaAdapterError


async def _publish_due_posts() -> None:
    async with async_session_factory() as db:
        due_posts = list(
            (
                await db.execute(
                    select(ScheduledPost).where(
                        ScheduledPost.status == "pending",
                        ScheduledPost.scheduled_at <= datetime.now(UTC),
                    )
                )
            ).scalars()
        )

        for post in due_posts:
            connection = (
                await db.execute(
                    select(PlatformConnection).where(
                        PlatformConnection.business_id == post.business_id,
                        PlatformConnection.platform == PlatformName.meta,
                    )
                )
            ).scalar_one_or_none()

            if connection is None or not connection.access_token_ref:
                post.status = "failed_no_connection"
                continue

            adapter = MetaAdapter(access_token=connection.access_token_ref)
            try:
                result = await adapter.create_post(
                    connection.external_id or "", post.content, post.media_url
                )
            except MetaAdapterError:
                post.status = "failed"
                continue

            post.status = "posted"
            post.posted_at = result.posted_at

        await db.commit()


@app.task(name="social.publish_due_posts")
def publish_due_posts_task() -> None:
    asyncio.run(_publish_due_posts())
