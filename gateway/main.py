"""
gateway/main.py

FastAPI entrypoint — routing/validation only per CODING_STANDARDS.md's
clean-separation rule (gateway -> services/*/ -> shared/models/). No
business logic belongs in this file or in route handlers generally.
"""
from __future__ import annotations

from fastapi import FastAPI

from gateway.api.v1 import health as health_v1

app = FastAPI(title="PRESENCE Gateway", version="0.1.0")

app.include_router(health_v1.router, prefix="/api/v1")


@app.get("/healthz")
async def healthz() -> dict:
    """Liveness only — no dependency checks. See /api/v1/health for readiness."""
    return {"status": "ok"}
