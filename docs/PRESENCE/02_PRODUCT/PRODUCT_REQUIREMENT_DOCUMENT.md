# Product Requirement Document (v1)

## 1. Problem Statement
- Who: Salons/Spas/Gyms as v1 persona (best LTV:CAC after agency channel, less churn-volatile than F&B — see BUSINESS_MODEL.md)
- Pain: fragmented GBP/WhatsApp/Meta presence, zero attribution from marketing activity to actual footfall/revenue
- Why now: WhatsApp API cost structure stabilized post-2026 pricing changes, AI inference cost curve favorable, agency channel underserved in India specifically

## 2. Goals & Non-Goals (v1)
**Goals:**
- Prove attribution v0 works on ≥30 pilot accounts
- Prove agency white-label unit economics on ≥1 agency
- Achieve <8% monthly churn on pilot cohort

**Non-Goals (explicit):**
- NOT building marketplace/commission/payments in v1
- NOT building multi-location enterprise tier in v1
- NOT building consumer-facing discovery app

## 3. Personas
See USER_PERSONAS.md — 2 personas for v1: SMB Owner, Agency Account Manager.

## 4. Functional Requirements
Mapped to API contracts in 03_ARCHITECTURE/API_STANDARDS.md and phase-tagged modules in 06_MODULES/. Core v1 scope: GBP read+respond, WhatsApp automation (review-request triggers, drip sequences), Meta read+scheduled-post, AI review-response drafting, attribution v0 (proxy signals), agency multi-client console.

## 5. Non-Functional Requirements
| Requirement | Target |
|---|---|
| Uptime | 99.5% (not 99.99% — don't over-engineer v1) |
| GBP/Meta sync latency | <15 min |
| AI response drafting latency | <8 sec p95 |
| WhatsApp delivery tracking | Real-time via webhook |

## 6. Success Metrics
- North Star: Net Revenue Retention (not signups)
- Guardrail: CAC payback <7 months (average-case model target)

## 7. Out-of-Scope / Deferred
See ROADMAP.md and 06_MODULES/ phase tags. Full list: marketplace, commission revenue, loyalty/cross-promotion network, franchise tooling, full multi-touch attribution (v0 is proxy-signal only), third-party API/integration layer.
