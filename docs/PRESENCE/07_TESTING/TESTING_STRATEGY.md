# Testing Strategy — Phased Rigor (overrides "90%+ coverage on everything, day one" mandate)

## Why Phased, Not Blanket-Maximum
A prior draft mandated Google/Stripe-grade rigor (90%+ coverage, full unit/integration/E2E/security/performance/accessibility/regression testing) on every feature from day one. This company hasn't completed Phase 0 validation yet — committing that rigor now means burning runway on test infrastructure for a product that may still pivot on segment/pricing/churn assumptions. This is a sequencing correction, not a quality downgrade.

## Rigor by Phase
| Phase | Bar |
|---|---|
| Phase 0–1 (pre-PMF, MVP) | **Attribution engine + billing/credit-ledger: high rigor from day one** (unit + property-based tests, per CLAUDE.md — a silent bug here costs a customer relationship or a compliance incident). Everything else: pragmatic — tests for critical paths, not blanket 90%+ coverage. Ship, learn, iterate. |
| Phase 2 (pilot, 30–50 customers) | Raise the bar on whatever real pilot usage shows is breaking. Add integration tests around GBP/Meta/WhatsApp sync as real edge cases surface. |
| Phase 3+ (agency-channel scale, Series A prep) | Full enterprise-grade bar: E2E, security, performance, accessibility, regression testing as standard — now appropriate because there's proof, revenue, and a reason to protect uptime/security at that level. |

## Test Pyramid Weighting (Phase 1)
Weighted toward attribution-correlation logic and BSP adapters — not toward UI snapshot tests. A subtly wrong correlation calculation silently destroys product credibility with zero visible error; a BSP webhook regression silently breaks message delivery. These get property-based testing (hypothesis) and fixture-based provider tests respectively. See 05_ENGINEERING/BACKEND_STANDARDS.md for the adapter testing requirement.

## CI Gate (Phase 1)
No merge to `main` without attribution-engine and billing test suites passing at 100%. Everything else is a warning, not a hard block, at this phase — this changes at Phase 2+ per GIT_STANDARDS.md.
