# Build Roadmap

## Phase 0 — Validation Sprint (Weeks 1–4) — NOT YET COMPLETE
- Structured Pune business census (Google Places API pull across 14 ranked areas)
- 25–30 SMB owner calls: real churn/WTP history, not hypothetical willingness
- Agency pre-sell: 3–5 conversations in existing network, gauge real interest
- BSP/API technical spike: Gallabox + GBP + Meta Graph API read, confirm abstraction pattern

**Exit criteria:** <8,000 addressable businesses across the 14 areas, or F&B churn consistently >8%/mo → revisit segment prioritization before Phase 1.

## Phase 1 — MVP Build (Months 1–4)
Core: sync engine (GBP/Meta/WhatsApp read+write), attribution v0 (proxy signals — direction requests, call-tracking, WhatsApp-campaign correlation), AI layer (cached review-response drafting, content gen), agency console (multi-client switcher, white-label branding). Explicitly OUT: payments, marketplace, multi-location enterprise tier, full MTA.

## Phase 2 — Pilot & Case-Study Generation (Months 4–7)
30–50 paying customers in Baner + Koregaon Park. Weekly attribution-data reviews. 1–2 agency pilots live with real sub-accounts. Cohort-retention dashboard operational by month 5.

**Exit criteria:** ≥85% pilot cohort retained at day 90, ≥1 agency actively reselling with ≥5 sub-accounts, ≥3 real attribution case studies.

## Phase 2.5 — Consumer Discovery (Hyperlocal Engine) — spec'd, build gated (2026-07-04)

Not a scheduled build phase — a gate check evaluated at the Phase 2 exit
boundary. See `06_MODULES/HYPERLOCAL_ENGINE.md` for the full spec and
`06_MODULES/CUSTOMER.md` Part 2 for the consumer-identity layer it depends
on. Ganesh approved this as a planned future product surface (third
persona, see `02_PRODUCT/USER_PERSONAS.md` Persona C); Phase 1–2 engineering
time is not diverted to it.

**Entry criteria (evaluated using real Phase 2 pilot data, not projections):**
at least one micro-geo with ≥15–20 PRESENCE-managed businesses and median
≥10 synced reviews with real rating spread — see `HYPERLOCAL_ENGINE.md` for
the full bar. If Phase 2 doesn't clear this, this phase is re-evaluated at
the next phase boundary rather than started anyway.

**If triggered:** build `services/discovery-engine/` (read-only discovery
over existing business/review data), the `consumers` identity layer, and
the discovery API surface — all per the module specs. Bookings, payments,
loyalty, consumer-authored reviews, and paid placement remain out of scope
even if this phase triggers — those still need their own separate override
conversation per `CLAUDE.md`.

## Phase 3 — Agency-Channel Scale (Months 7–18)
Dedicated Agency Partnerships hire. Formalized white-label product. Geographic expansion per GTM_STRATEGY.md. Introduce Scale tier once 2–3 genuine multi-branch reference accounts exist.

## Phase 4 — Series A Readiness (Months 18–24)
Target: ₹8–15 Cr ARR run-rate, ≥40% of new ARR from agency channel, gross margin trending 70%+, documented cohort retention curves (not projections). API/integration layer only now, once real partner demand exists.

## Full Financial Scenarios
See business model financial projection (external — 3-year worst/average/best case with CAC payback, burn rate, break-even by scenario).
