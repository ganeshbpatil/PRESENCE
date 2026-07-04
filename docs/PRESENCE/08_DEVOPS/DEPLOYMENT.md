# Deployment

Existing Hostinger VPS, Docker Compose, Traefik reverse proxy — see repo root `docker-compose.yml`. Isolated Postgres/Redis instances from AgencyOS/skyiDM per the existing Pattern-A convention (separate blast radius). Staging: shared VPS namespace, isolated schema. Production: dedicated Postgres instance, resource-limited containers, Traefik rate-limiting middleware on public-facing webhook endpoints (WhatsApp/Meta/Razorpay webhooks specifically).

**Given the portfolio now includes AgencyOS, skyiDM, and PRESENCE on the same VPS class of infrastructure:** invest 2–3 days building a shared internal deployment template/Makefile across all three rather than solving deployment separately per project — a real operational-efficiency win consistent with a reusable-frameworks-over-one-off-solutions approach.

## Vault (one-time, manual — do not automate in CI)

`docker-compose.yml` includes a `vault` service (self-hosted secrets store for platform access tokens — see `SECURITY_ARCHITECTURE.md`). After the stack's first `docker compose up -d vault`, run `scripts/vault-init.sh` by hand: it initializes Vault, prints the unseal keys + root token (capture them in a password manager immediately, they are shown once), enables KV v2 + AppRole, and prints a `VAULT_ROLE_ID`/`VAULT_SECRET_ID` pair to add to `.env`. Restart `gateway`/`celery-worker`/`celery-beat` afterward so they pick up the new env vars.

Vault comes back **sealed** after every container restart or host reboot (no cloud KMS auto-unseal on this VPS) — run `docker compose exec vault vault operator unseal` three times with unseal keys before any vault-dependent feature (storing/reading a Meta/GBP/WhatsApp platform token) works again. Nothing else in the stack is blocked by a sealed Vault.

## CI/CD deploy secrets (currently unconfigured)

`.github/workflows/ci-cd.yml`'s `deploy-staging`/`deploy-production` jobs fail on every push to `main` ("missing server host") because the required repo secrets were never added: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_STAGING_DIR`, `VPS_PRODUCTION_DIR` (see `gh secret list` — empty as of 2026-07-04). `test`/`build` jobs still run and gate merges correctly. Until these are configured, deploy by hand on the VPS: `cd /docker/presence && git pull && docker compose build && docker compose up -d` (or `./scripts/deploy.sh`).
