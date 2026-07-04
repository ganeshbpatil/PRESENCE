"""
Smoke test for the gateway's health endpoints. Runs against real
Postgres/Redis (see .github/workflows/ci.yml service containers) rather
than mocks — these two endpoints exist specifically to prove connectivity,
so a mocked test would prove nothing.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from gateway.main import app


@pytest.mark.asyncio
async def test_healthz_liveness():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_checks_db_and_redis():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "database": "ok", "redis": "ok"}
