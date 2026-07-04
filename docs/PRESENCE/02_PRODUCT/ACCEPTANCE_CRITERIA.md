# Acceptance Criteria — P0 Screens/Features

## Attribution Dashboard
- [ ] Leads with a single "estimated revenue impact this month" headline number, not a chart wall
- [ ] Drill-down available for agency users, not forced on SMB owner view
- [ ] `signal_completeness_pct` visibly surfaced or used to caveat confidence when low
- [ ] Loads in <3s on a 4G connection (Pune-realistic network conditions)

## WhatsApp Campaign Builder
- [ ] Template-first UX — user picks a proven template by default, freeform composition is secondary
- [ ] Shows estimated cost (via `estimate_cost_inr`) before send, debited from credit ledger pre-flight
- [ ] Never sends outside an open service window without explicit category classification shown to the user

## Agency Multi-Client Console
- [ ] Client switch is one click, not a navigation flow (agencies manage 20–50 accounts — friction compounds)
- [ ] White-label branding (logo/colors) applies correctly across the SMB-facing views the agency's clients see
- [ ] Consolidated report exportable (PDF/CSV minimum for v1)

## Review Inbox
- [ ] AI draft appears within 8s p95 of a new review syncing
- [ ] Draft-then-approve only — no auto-send toggle exists in v1 UI at all (not just defaulted off)

## Onboarding/Connect Flow
- [ ] Single guided flow covering GBP + Meta + WhatsApp OAuth — measure drop-off per step explicitly from week 1
- [ ] First sync completes and is visible to the user within the 15-min NFR, with a visible progress state, not a silent wait
