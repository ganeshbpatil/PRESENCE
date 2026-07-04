"""
gateway/db.py's async engine/pool is a module-level singleton, but
pytest-asyncio (function-scoped by default) gives each test its own event
loop. A pooled asyncpg connection checked out under one test's loop can't
be reused once that loop closes ("Future attached to a different loop").
Disposing the pool at the end of every test — while its own loop is still
open — guarantees no connection ever survives into the next test's loop.
"""
import pytest_asyncio

from gateway.db import engine


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()
