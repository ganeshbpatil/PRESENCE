"""
gateway/celery_app.py

Celery app shared by the gateway (task producer), celery-worker, and
celery-beat services in docker-compose.yml. Task modules register via
`app.autodiscover_tasks([...])` as service folders gain tasks — none yet
(Phase 0 scaffolding).
"""
from __future__ import annotations

from celery import Celery

from gateway.config import get_settings

settings = get_settings()

app = Celery(
    "presence",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
app.conf.timezone = "UTC"
app.conf.enable_utc = True
