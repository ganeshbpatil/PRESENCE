# Deployment

Existing Hostinger VPS, Docker Compose, Traefik reverse proxy — see repo root `docker-compose.yml`. Isolated Postgres/Redis instances from AgencyOS/skyiDM per the existing Pattern-A convention (separate blast radius). Staging: shared VPS namespace, isolated schema. Production: dedicated Postgres instance, resource-limited containers, Traefik rate-limiting middleware on public-facing webhook endpoints (WhatsApp/Meta/Razorpay webhooks specifically).

**Given the portfolio now includes AgencyOS, skyiDM, and PRESENCE on the same VPS class of infrastructure:** invest 2–3 days building a shared internal deployment template/Makefile across all three rather than solving deployment separately per project — a real operational-efficiency win consistent with a reusable-frameworks-over-one-off-solutions approach.
