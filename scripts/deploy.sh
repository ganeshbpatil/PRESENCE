#!/usr/bin/env bash
# scripts/deploy.sh
#
# Runs ON the Hostinger VPS (invoked over SSH by
# .github/workflows/ci-cd.yml, or by hand). Builds and (re)starts the
# PRESENCE stack in place. Assumes the repo is already checked out at
# $DEPLOY_DIR and .env already exists there with real secrets — this
# script never creates or edits .env (see SECURITY_ARCHITECTURE.md:
# production secrets are not committed or templated here).
set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$DEPLOY_DIR"

if [ ! -f .env ]; then
  echo "ERROR: .env not found in $DEPLOY_DIR — copy .env.example and fill in real secrets first." >&2
  exit 1
fi

if ! docker network inspect traefik-public >/dev/null 2>&1; then
  echo "ERROR: external network 'traefik-public' not found — this VPS's shared Traefik" >&2
  echo "instance (used by AgencyOS/skyiDM too, per Pattern-A convention) must exist first." >&2
  exit 1
fi

echo "==> Pulling latest code"
git fetch origin
git checkout "${DEPLOY_BRANCH:-main}"
git pull --ff-only origin "${DEPLOY_BRANCH:-main}"

echo "==> Building images"
docker compose build

echo "==> Applying database migrations"
docker compose run --rm gateway alembic upgrade head

echo "==> Starting stack"
docker compose up -d

echo "==> Pruning old images"
docker image prune -f

echo "==> Waiting for gateway health check"
for _ in $(seq 1 30); do
  if docker compose exec -T gateway python -c "
import urllib.request
urllib.request.urlopen('http://localhost:8000/healthz', timeout=2)
" >/dev/null 2>&1; then
    echo "==> Deploy complete, gateway is healthy"
    exit 0
  fi
  sleep 2
done

echo "ERROR: gateway did not become healthy within 60s — check 'docker compose logs gateway'" >&2
exit 1
