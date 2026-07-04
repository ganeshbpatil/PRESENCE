"""
gateway/tasks/sync.py's _publish_due_posts, tested at the function level
(not via Celery) with an injected fake VaultClient -- real Meta publishing
stays untested end-to-end per test_social.py's existing precedent (needs a
real access token), but the vault-resolution step ahead of it is fully
local and worth covering: a resolution failure must fail that one post,
not crash the whole beat task.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from gateway.db import async_session_factory
from gateway.tasks.sync import _publish_due_posts
from shared.models.core import (
    Business,
    BusinessCategory,
    BusinessTier,
    PlatformConnection,
    PlatformName,
    ScheduledPost,
    SyncStatus,
)
from shared.secrets.vault_client import VaultError


class _RaisingVaultClient:
    async def resolve(self, ref: str) -> str:
        raise VaultError("vault sealed")


async def _make_business_with_due_post() -> tuple[uuid.UUID, uuid.UUID]:
    async with async_session_factory() as db:
        business = Business(
            name=f"Publish Task Test {uuid.uuid4()}",
            category=BusinessCategory.salon_spa_gym,
            tier=BusinessTier.starter,
        )
        db.add(business)
        await db.flush()

        db.add(
            PlatformConnection(
                business_id=business.id,
                platform=PlatformName.meta,
                external_id="page-123",
                access_token_ref=f"platform-connections/{business.id}/meta",
                sync_status=SyncStatus.healthy,
            )
        )
        post = ScheduledPost(
            business_id=business.id,
            platform="meta",
            content="Due post",
            scheduled_at=datetime.now(UTC) - timedelta(minutes=1),
            status="pending",
        )
        db.add(post)
        await db.commit()
        return business.id, post.id


@pytest.mark.asyncio
async def test_vault_resolution_failure_marks_post_failed_not_crashed():
    _business_id, post_id = await _make_business_with_due_post()

    await _publish_due_posts(vault=_RaisingVaultClient())

    async with async_session_factory() as db:
        refreshed = await db.get(ScheduledPost, post_id)
        assert refreshed.status == "failed"
        assert refreshed.posted_at is None


@pytest.mark.asyncio
async def test_post_with_no_connection_is_marked_failed_no_connection():
    async with async_session_factory() as db:
        business = Business(
            name=f"No Connection Test {uuid.uuid4()}",
            category=BusinessCategory.salon_spa_gym,
            tier=BusinessTier.starter,
        )
        db.add(business)
        await db.flush()
        post = ScheduledPost(
            business_id=business.id,
            platform="meta",
            content="Orphan post",
            scheduled_at=datetime.now(UTC) - timedelta(minutes=1),
            status="pending",
        )
        db.add(post)
        await db.commit()
        post_id = post.id

    await _publish_due_posts(vault=_RaisingVaultClient())

    async with async_session_factory() as db:
        refreshed = await db.get(ScheduledPost, post_id)
        assert refreshed.status == "failed_no_connection"
