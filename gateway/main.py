"""
gateway/main.py

FastAPI entrypoint — routing/validation only per CODING_STANDARDS.md's
clean-separation rule (gateway -> services/*/ -> shared/models/). No
business logic belongs in this file or in route handlers generally.
"""
from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from gateway import metrics as metrics_v1
from gateway.api.v1 import agencies as agencies_v1
from gateway.api.v1 import attribution as attribution_v1
from gateway.api.v1 import auth as auth_v1
from gateway.api.v1 import billing as billing_v1
from gateway.api.v1 import businesses as businesses_v1
from gateway.api.v1 import dashboard as dashboard_v1
from gateway.api.v1 import health as health_v1
from gateway.api.v1 import notifications as notifications_v1
from gateway.api.v1 import oauth as oauth_v1
from gateway.api.v1 import reviews as reviews_v1
from gateway.api.v1 import social as social_v1
from gateway.api.v1 import users as users_v1
from gateway.api.v1 import whatsapp as whatsapp_v1
from gateway.config import get_settings

app = FastAPI(title="PRESENCE Gateway", version="0.1.0")

_cors_origins = get_settings().cors_allowed_origins_list
if _cors_origins:
    # Only the admin-panel frontend's own origin(s) need this -- public
    # webhook endpoints (WhatsApp/Meta/Razorpay) are server-to-server and
    # never go through a browser, so they're unaffected either way.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health_v1.router, prefix="/api/v1")
app.include_router(auth_v1.router, prefix="/api/v1")
app.include_router(businesses_v1.router, prefix="/api/v1")
app.include_router(billing_v1.router, prefix="/api/v1")
app.include_router(whatsapp_v1.router, prefix="/api/v1")
app.include_router(reviews_v1.router, prefix="/api/v1")
app.include_router(attribution_v1.router, prefix="/api/v1")
app.include_router(social_v1.router, prefix="/api/v1")
app.include_router(notifications_v1.router, prefix="/api/v1")
app.include_router(agencies_v1.router, prefix="/api/v1")
app.include_router(users_v1.router, prefix="/api/v1")
app.include_router(oauth_v1.router, prefix="/api/v1")
app.include_router(dashboard_v1.router, prefix="/api/v1")
app.include_router(metrics_v1.router)


@app.get("/healthz")
async def healthz() -> dict:
    """Liveness only — no dependency checks. See /api/v1/health for readiness."""
    return {"status": "ok"}
