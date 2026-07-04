# Docker

See repo root `docker-compose.yml`. Services: `postgres`, `redis`, `gateway` (FastAPI, Traefik-routed), `celery-worker`, `celery-beat`. All join an external `traefik-public` network for routing plus an internal `presence-internal` network for service-to-service communication that shouldn't be internet-exposed.

Rate-limiting middleware is applied at the Traefik label level on the `gateway` service specifically because public webhook endpoints (WhatsApp/Meta/Razorpay) live there — see `03_ARCHITECTURE/SECURITY_ARCHITECTURE.md` for why signature verification is still required in addition to rate-limiting, not instead of it.
