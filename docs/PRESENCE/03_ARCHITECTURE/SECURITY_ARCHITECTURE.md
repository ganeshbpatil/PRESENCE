# Security Architecture

## Auth: Self-built JWT + OAuth (not Clerk — see stack decision record)
Rationale: avoids per-MAU vendor cost at target scale (8,000–10,000 businesses × multiple staff logins by Year 3), keeps auth data in the same Postgres instance rather than a third-party auth vendor holding customer identity data — relevant given DPDP Act data-residency/handling considerations for Indian SMB and (for the clinic segment specifically) health-adjacent customer data.

## RBAC Roles (v1 minimum)
- SMB Owner (full access to own business)
- Agency Admin (multi-client access, white-label console)
- Agency Viewer (read-only, for junior agency staff)

## Webhook Security (non-negotiable)
Every public-facing webhook (WhatsApp BSP, Meta, Razorpay) MUST verify signature/token before processing payload. This is enforced at the adapter level (`adapters/whatsapp/base.py:parse_webhook`), never trust-by-default. Traefik rate-limiting is a second layer, not a substitute for signature verification.

## Secrets Management
No raw platform access tokens (GBP/Meta/WhatsApp) stored in application tables — `platform_connections.access_token_ref` is a reference into a vault/secrets store, never the raw token. `.env` for local/dev only; production secrets via a proper secrets manager (evaluate: Doppler, Infisical, or HashiCorp Vault self-hosted given existing VPS pattern — do not default to AWS Secrets Manager given the AWS non-adoption decision).

## Data Protection (DPDP Act consideration)
Customer PII (phone numbers, review text, WhatsApp opt-ins) requires documented consent handling — build this into the onboarding/connect flow from v1, not retrofitted. Clinic-segment data (health-adjacent) warrants extra caution even though PRESENCE isn't processing clinical data directly — customer contact/visit data in a healthcare context still carries elevated sensitivity expectations.

## Payment Security
Razorpay handles PCI-scope directly (decision already made during LocalEdge exploration — do not re-evaluate). PRESENCE never touches raw card data.
