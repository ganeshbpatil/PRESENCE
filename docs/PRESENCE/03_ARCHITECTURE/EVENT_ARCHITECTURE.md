# Event Architecture

## Bus Choice: Redis pub/sub (not Kafka)
Already running Redis for Celery — reuse it, don't add infra complexity until real volume justifies Kafka (Phase 3+ decision point, not now). Less durable than Kafka at very high volume; acceptable trade-off at MVP/pilot scale.

## Core Async Jobs (Celery)
- Scheduled sync jobs: GBP/Meta/WhatsApp pull on a schedule (target <15 min latency NFR)
- AI orchestrator calls: queued, not synchronous in the request path where drafting can tolerate async (review-response drafting can be async-then-notify; anything the user is actively waiting on in-UI should hit the <8s p95 target directly)
- Attribution correlation compute: triggered async (`POST /attribution/compute-correlation`), never computed synchronously in a request

## Event Types (internal pub/sub, not external webhooks)
- `platform.connection.degraded` — feeds the platform-health dashboard
- `review.received` — triggers AI-draft generation job
- `whatsapp.message.delivered` / `.failed` — updates credit ledger + delivery-status UI
- `business.churned` — triggers cohort-view refresh, potentially a win-back workflow later (not v1)

## External Webhooks (public-facing, rate-limited at Traefik per docker-compose.yml)
- WhatsApp BSP webhook (signature-verified before any processing — see `adapters/whatsapp/base.py`)
- Meta webhook (verify token check)
- Razorpay webhook (signature-verified)

Never trust an unverified external webhook payload — this is explicitly called out because it's a public internet-facing surface with real financial/data implications if bypassed.
