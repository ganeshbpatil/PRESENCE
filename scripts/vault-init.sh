#!/usr/bin/env bash
# scripts/vault-init.sh
#
# One-time setup for the presence-internal Vault container. Run this BY
# HAND on the VPS, once, after `docker compose up -d vault` -- never from
# CI, never by an automated agent. It prints the unseal keys and root
# token: capture those in a password manager immediately, they are not
# saved anywhere by this script and cannot be recovered if lost (you'd
# have to wipe the presence-vault-data volume and start over).
#
# After this script finishes, put the printed VAULT_ROLE_ID/VAULT_SECRET_ID
# into .env and restart gateway/celery so they pick it up.
set -euo pipefail

COMPOSE="docker compose"
KV_MOUNT="presence-secrets"
POLICY_NAME="presence-gateway"
ROLE_NAME="presence-gateway"

run() { $COMPOSE exec -T vault "$@"; }

echo "== 1/6: vault operator init =="
echo "Capture the 5 unseal keys and the root token below NOW -- they will"
echo "not be shown again and are not written to disk by this script."
read -rp "Press enter once you're ready to see them... "
run vault operator init -key-shares=5 -key-threshold=3

echo
echo "== 2/6: unseal (enter 3 of the 5 keys just printed) =="
for i in 1 2 3; do
  read -rsp "Unseal key $i: " key
  echo
  run vault operator unseal "$key"
done

echo
read -rsp "Root token (from step 1, needed for the one-time setup below): " root_token
echo

echo "== 3/6: enable KV v2 at ${KV_MOUNT}/ =="
run vault login -no-print "$root_token"
run vault secrets enable -path="$KV_MOUNT" -version=2 kv || echo "(already enabled, continuing)"

echo "== 4/6: policy scoped to platform-connections/* only =="
cat <<EOF | $COMPOSE exec -T vault vault policy write "$POLICY_NAME" -
path "${KV_MOUNT}/data/platform-connections/*" {
  capabilities = ["create", "read", "update"]
}
EOF

echo "== 5/6: enable AppRole auth + role bound to that policy =="
run vault auth enable approle || echo "(already enabled, continuing)"
run vault write "auth/approle/role/${ROLE_NAME}" \
  token_policies="$POLICY_NAME" \
  token_ttl=1h \
  token_max_ttl=4h

echo "== 6/6: role_id / secret_id for .env =="
echo "VAULT_ROLE_ID=$(run vault read -field=role_id "auth/approle/role/${ROLE_NAME}/role-id")"
run vault write -f "auth/approle/role/${ROLE_NAME}/secret-id" -format=json \
  | grep -A1 '"secret_id"' | head -1 \
  | sed 's/.*: "\(.*\)".*/VAULT_SECRET_ID=\1/'

echo
echo "Done. Add the VAULT_ROLE_ID / VAULT_SECRET_ID lines above to .env,"
echo "then: docker compose up -d gateway celery-worker celery-beat"
echo
echo "Remember: after every 'docker compose restart vault' or host reboot,"
echo "vault comes back sealed -- run:"
echo "  docker compose exec vault vault operator unseal   (x3, different keys each time is fine)"
