# API Standards

## Principles
- API-first, documentation-first: OpenAPI spec (`docs/openapi.yaml`, to be generated) is the source of truth. Regenerate the spec when adding endpoints — don't let it drift from actual routes.
- REST, versioned under `/api/v1/`. No breaking changes within a version — additive only; new major version for breaking changes.
- Attribution-engine endpoints are versioned/namespaced separately from sync-engine endpoints — deliberate, so this service can be extracted or licensed independently later without an API-contract rewrite.

## Representative Contract (expand in openapi.yaml, not here)
```
# Sync Engine
POST   /api/v1/businesses/{id}/connections
GET    /api/v1/businesses/{id}/connections/health

# Reviews / AI
GET    /api/v1/businesses/{id}/reviews
POST   /api/v1/reviews/{id}/draft-response
POST   /api/v1/reviews/{id}/send-response

# Attribution Engine (isolated, internal auth)
GET    /api/v1/businesses/{id}/attribution/summary
POST   /api/v1/attribution/compute-correlation

# WhatsApp / Billing
POST   /api/v1/campaigns
GET    /api/v1/credit-ledger/{business_id}/balance

# Agency Console
GET    /api/v1/agencies/{id}/businesses
GET    /api/v1/agencies/{id}/consolidated-report
```

## Frontend Contract Generation
Typed API client generated FROM the OpenAPI spec (openapi-typescript or equivalent) — eliminates frontend/backend contract-drift bugs, which matters more here than usual because attribution-engine and sync-engine evolve on different cadences.

## Auth on APIs
JWT bearer tokens, RBAC-scoped (owner/agency-admin/agency-viewer roles minimum for v1). Internal service-to-service calls (e.g., gateway → attribution-engine) use a separate internal auth scheme, not the same user-facing JWT.
