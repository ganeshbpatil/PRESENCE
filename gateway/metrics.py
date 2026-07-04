"""
gateway/metrics.py

Prometheus /metrics endpoint per docs/PRESENCE/08_DEVOPS/MONITORING.md
(self-hosted Prometheus/Grafana) — surfaces the AI orchestrator's
ai_cache_hit_total/ai_cache_miss_total counters, which AI.md calls out
explicitly ("<60% hit rate flags a margin risk investigation, not just a
dashboard nicety").

Registered without the /api/v1 prefix in main.py, matching /healthz's
top-level convention (Prometheus scrape targets expect a bare path).
"""
from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
