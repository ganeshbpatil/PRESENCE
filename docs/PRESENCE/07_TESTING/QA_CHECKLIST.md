# QA Checklist (pre-pilot, Phase 1 → 2 gate)

- [ ] Attribution correlation math validated against at least 3 known-good manual calculations
- [ ] BSP webhook signature verification tested with both valid and tampered payloads
- [ ] Credit ledger: concurrency test confirms no race condition under simultaneous debits
- [ ] Onboarding connect flow tested end-to-end for all 3 platforms (GBP, Meta, WhatsApp) with both success and failure/revoked-permission paths
- [ ] Draft-then-approve flow confirmed to have zero auto-send code path reachable in v1 UI
- [ ] Cohort retention view returns correct numbers against a manually-verified seed dataset
- [ ] Platform-health dashboard correctly reflects a manually-degraded connection (test by revoking a sandbox API token)
