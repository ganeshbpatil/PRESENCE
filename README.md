# PRESENCE

AI-powered hyperlocal business operating system for the India SMB market.
Full strategic and technical context lives in `docs/PRESENCE/` — start with
`docs/PRESENCE/00_PROJECT_OVERVIEW/PROJECT_OVERVIEW.md`. Claude Code session
memory/conventions live in `CLAUDE.md`.

**Status:** Phase 0 (pre-PMF scaffolding). `gateway/` is a minimal FastAPI
skeleton (health checks + DB/Redis wiring) — feature endpoints, the
attribution engine, and the sync-engine adapters are not built yet.

## Local development

Requires Docker and Docker Compose.

```bash
cp .env.example .env
# fill in POSTGRES_PASSWORD at minimum; other secrets only needed once
# you're actually wiring the corresponding integration (Gallabox, GBP, etc)

docker network create traefik-public  # first time only, if not already present

docker compose build
docker compose run --rm gateway alembic upgrade head
docker compose up -d
```

The gateway is then reachable at `http://localhost:8000` if you're running
without Traefik in front of it (add a port mapping locally), or at
`https://${PRESENCE_API_DOMAIN}` once Traefik and DNS are wired up.

- `GET /healthz` — liveness, no dependency checks
- `GET /api/v1/health` — readiness, verifies Postgres + Redis connectivity

Run tests and lint the same way CI does:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check .
pytest -v          # needs Postgres/Redis reachable at the DATABASE_URL/REDIS_URL in your env
```

## Database migrations

`shared/models/core.py` is the single source of truth for schema — never
hand-write a migration independently of it (see
`docs/PRESENCE/03_ARCHITECTURE/DATABASE_ARCHITECTURE.md`).

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Deploying to the VPS

PRESENCE joins the existing Hostinger VPS (Docker Compose + Traefik) already
running AgencyOS/skyiDM, in isolated containers with its own Postgres/Redis
per the Pattern-A convention — see
`docs/PRESENCE/08_DEVOPS/DEPLOYMENT.md`.

One-time setup on the VPS:

```bash
git clone <this repo> /opt/presence   # or wherever the other Pattern-A projects live
cd /opt/presence
cp .env.example .env   # fill in real production secrets — never commit this file
docker network inspect traefik-public   # confirm the shared Traefik network already exists
```

Then either run `./scripts/deploy.sh` by hand on the VPS, or let
`.github/workflows/ci-cd.yml` do it — that workflow builds on every push to
`main`, auto-deploys to staging, then waits for manual approval (configure a
`production` GitHub Environment with required reviewers in repo Settings ->
Environments) before deploying to production. It expects these repo secrets:

| Secret | Purpose |
|---|---|
| `VPS_HOST` | SSH host for the VPS |
| `VPS_USER` | SSH user |
| `VPS_SSH_KEY` | Private key for that user |
| `VPS_STAGING_DIR` | Path to the staging checkout on the VPS |
| `VPS_PRODUCTION_DIR` | Path to the production checkout on the VPS |

`scripts/deploy.sh` pulls latest `main`, rebuilds images, runs Alembic
migrations, restarts the stack, and waits for `/healthz` before reporting
success.
