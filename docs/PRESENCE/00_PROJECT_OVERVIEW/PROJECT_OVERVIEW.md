# PRESENCE — Project Overview

**Status:** Architecture approved. Two decisions locked this session (below). This doc tree is the single source of truth per the CTO operating charter — if any doc conflicts with another, stop and reconcile before building; never guess.

## What This Is
AI-powered hyperlocal business operating system for India SMBs. Wedge: reputation-to-revenue attribution + WhatsApp-native automation, distributed primarily through an agency white-label channel — deliberately NOT a generic "manage your GBP/social/WhatsApp" tool, which is commoditized (see `01_BUSINESS/COMPETITOR_ANALYSIS.md`).

## Two Decisions Locked This Session (do not relitigate without a genuinely new reason)

### Decision 1 — Tech Stack: FastAPI/Python, not NestJS/Prisma/Clerk/AWS
An earlier "CTO system prompt" draft specified NestJS + Prisma + Clerk + Cloudflare R2 + Stripe + AWS. That conflicted with the already-scaffolded FastAPI + SQLAlchemy + Celery + Postgres + Razorpay stack running on the existing Hostinger VPS/Traefik/Docker setup shared with AgencyOS/skyiDM/Hermes.

**Resolved: keep FastAPI/Python.** Reuses existing infra (holds the margin model's near-zero marginal infra cost assumption), keeps one primary backend language across the venture portfolio, avoids Clerk's per-MAU cost compounding at the 8,000–10,000 customer Year-3 target, avoids re-deriving unit economics from scratch. Full trade-off table: `03_ARCHITECTURE/SYSTEM_ARCHITECTURE.md`.

### Decision 2 — Module Scope: Phased, not all-day-1
The original module list included Offers, Marketplace-adjacent (Hyperlocal Engine), Payments, and Search as full day-1 modules.

**Resolved: phased**, per the deferral list already established. Every module doc in `06_MODULES/` is tagged **P0** (build now), **P1** (Phase 2), or **DEFERRED** (Phase 3+, do not build without an explicit override conversation).

## Engineering Rigor — Phased, Not Blanket-Maximum
A prior draft mandated "never optimize for speed, 90%+ coverage on every feature, Google/Stripe-grade rigor from day one." Overridden: rigor ramps with proof stage — attribution-engine and billing/credit-ledger are high-rigor from day one regardless of phase (silent bugs there are existential); everything else follows a graduated bar that reaches full enterprise-grade only at Phase 3+ (post-agency-channel-traction). Full table: `07_TESTING/TESTING_STRATEGY.md`. This is sequencing, not lowered ambition.

## Current Build Phase
**Phase 0 (validation) — not yet complete.** Pune business census, SMB churn/WTP calls, and agency pre-sell conversations are still outstanding. Do not over-invest engineering effort in segments or features whose underlying assumptions (churn rate, ACV, segment priority) haven't been validated against real data yet. See `01_BUSINESS/ROADMAP.md`.

## Doc Map
- `01_BUSINESS/` — vision, market, competitors, business model, GTM, roadmap
- `02_PRODUCT/` — PRD, personas, journeys, feature list (phased), acceptance criteria
- `03_ARCHITECTURE/` — system design, DB, events, API standards, security
- `04_DESIGN/` — design system, UI/UX guidelines, component library
- `05_ENGINEERING/` — coding, backend, frontend, DB, git standards
- `06_MODULES/` — one doc per module, each phase-tagged
- `07_TESTING/` — strategy, QA checklist, performance, security testing
- `08_DEVOPS/` — deployment, infra decision record, Docker, CI/CD, monitoring
