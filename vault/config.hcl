// vault/config.hcl
//
// Single-node Vault server config for the presence-internal docker network.
// tls_disable=true is deliberate here, not an oversight: this listener is
// only reachable from other containers on the isolated `presence-internal`
// bridge network (see docker-compose.yml) -- it has no port mapping to the
// host and no route from `traefik-public`, so it is never internet-facing,
// matching the existing no-TLS-internally posture already used for
// Postgres/Redis on this stack. Revisit if Vault is ever exposed beyond
// this single VPS's internal network.
storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

api_addr = "http://vault:8200"
ui       = false

