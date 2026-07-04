# PRESENCE — Claude Code Project Memory

> This file is read by Claude Code at the start of every session. Keep it current —
> stale context here is worse than no context. Update the "Current State" section
> after every session, not just when something breaks.

## What This Is

PRESENCE — AI-powered hyperlocal business operating system (India SMB market).
Wedge: reputation-to-revenue attribution + WhatsApp-native automation for local
SMBs (salons, clinics, gyms, F&B, retail), distributed primarily through an
agency white-label channel. Full strategic and technical context lives in
`docs/PRESENCE/` — a numbered doc tree (00_PROJECT_OVERVIEW through
08_DEVOPS). Read `docs/PRESENCE/00_PROJECT_OVERVIEW/PROJECT_OVERVIEW.md`
first every session — it states the two locked architecture decisions
(FastAPI/Python stack, phased module scope) and links everything else. Do
not re-derive strategy that's already decided there; execute against it.
Every module in `docs/PRESENCE/06_MODULES/` is phase-tagged (P0/P1/DEFERRED)
— check the tag before building anything in a module marked DEFERRED.

## Non-Negotiable Architecture Principles

These come from explicit risk analysis — do not relitigate them without flagging
the trade-off to Ganesh first:

1. **GBP/Meta are sync sources, never system of record.** Canonical customer/
   review/insight data lives in our Postgres. If a platform API degrades, the
   product degrades to read-only, it does not break. Never write code that
   assumes GBP/Meta as the source of truth for anything.

2. **WhatsApp BSP is abstracted behind an interface.** `services/sync-engine/
   adapters/whatsapp/base.py` defines the contract. New BSP = new adapter file,
   zero changes to any calling code. Currently implemented: Gallabox (primary,
   per prior SKYi experience). Gupshup/Interakt are stubs — do not hardcode
   Gallabox-specific fields outside `gallabox.py`.

3. **Attribution engine is a separate service, not embedded in sync-engine.**
   This is the defensible IP. Keep it decoupled — it should be extractable/
   licensable independently later. Internal API calls between services are
   fine; shared database tables/models between attribution-engine and
   sync-engine are not.

4. **AI orchestrator is cache-first and model-agnostic.** Gross margin is
   directly a function of cache-hit rate (see unit economics in diligence
   memo). Never add an LLM call without checking whether it's templatable/
   cacheable first. Provider routing goes through `router.py` — no direct
   OpenRouter/Anthropic SDK calls from feature code.

5. **Credit ledger is append-only.** Never `UPDATE balance` directly — always
   insert a new ledger row and compute `balance_after`. This is a hard rule,
   not a style preference (concurrency + audit trail).

## Current State

<!-- UPDATE THIS SECTION EVERY SESSION -->
- Phase: 0 (pre-PMF), but core modules are implemented, not just scaffolded
- Last completed: JWT auth, Razorpay billing + append-only credit ledger,
  attribution-engine v0 correlation (proxy signals), Gallabox WhatsApp
  webhook/campaign send, Meta social adapter (insights + basic posting),
  review-response drafting via ai-orchestrator, in-app/email notifications.
  Alembic migrations for all of the above. 36 passing tests. Deployed live
  at https://presence.srv1000510.hstgr.cloud/ (merged via PR #2). Separately,
  Customer/Marketplace scope decision (see decision log below) spec'd into
  `USER_PERSONAS.md`, `06_MODULES/CUSTOMER.md`, `06_MODULES/HYPERLOCAL_ENGINE.md`,
  `01_BUSINESS/ROADMAP.md` Phase 2.5 — docs only, no build yet (see gate below).
- In progress: —
- Next up: wire up a real secrets vault for platform access tokens (Meta
  adapter currently takes a raw token — see
  services/sync-engine/adapters/social/meta.py's module docstring for the
  flagged gap against SECURITY_ARCHITECTURE.md); configure the GitHub
  Actions VPS_* secrets so the CI/CD auto-deploy pipeline actually runs
  (currently unconfigured — deploy-staging/production jobs fail with
  "missing server host"; the live site is being updated by hand via
  `docker compose` on the VPS instead); first Gallabox adapter hardening;
  attribution v0 signal capture depth
- Known issues / tech debt: CI/CD deploy-staging and deploy-production jobs
  fail on every push to main because the required repo secrets (VPS_HOST,
  VPS_USER, VPS_SSH_KEY, VPS_STAGING_DIR, VPS_PRODUCTION_DIR) were never
  added — test/build jobs still pass and gate merges correctly, only the
  deploy step is a no-op failure right now. Separately, `BUSINESS_MODEL.md`,
  PRD non-goals, `FEATURE_LIST.md`, `COMPETITOR_ANALYSIS.md` still describe
  the pre-2026-07-04 no-marketplace position and haven't been reconciled
  with the decision log below yet.
- Blocked on: Phase 0 validation research (Pune census, SMB churn calls,
  agency pre-sell) — do not over-invest in features that depend on unvalidated
  segment/pricing assumptions until Phase 0 exit criteria are met. Hyperlocal
  Engine build work is separately blocked on its own Phase 2 density trigger
  regardless of Phase 0 status (see `06_MODULES/HYPERLOCAL_ENGINE.md`)

## Tech Stack (do not deviate without discussion)

- **Backend:** FastAPI (Python 3.11+), SQLAlchemy 2.0, Alembic, Celery, Redis
- **DB:** PostgreSQL 15+ — dedicated instance, isolated from AgencyOS/skyiDM
  prod per existing Pattern-A convention
- **Frontend:** Next.js 15, Tailwind, shadcn/ui, TanStack Query — reuse
  AgencyOS design system components where possible, don't fork a new one
- **Infra:** Docker Compose, Traefik (existing VPS setup), deployed on the
  same Hostinger VPS as AgencyOS/skyiDM but isolated containers/DB
- **AI:** OpenRouter as primary router, Anthropic direct as fallback/premium
  path — all calls go through `ai-orchestrator`, never direct from features
- **Payments:** Razorpay (decision already made during LocalEdge exploration
  — do not re-evaluate PGs)
- **WhatsApp:** Gallabox as primary BSP (existing relationship/experience)

## Conventions

- All money amounts stored as `NUMERIC`, never `FLOAT` — this is a billing
  system, floating point errors are unacceptable
- All timestamps `TIMESTAMPTZ`, UTC — no naive datetimes anywhere
- All external platform IDs (GBP location ID, Meta page ID, WA phone ID)
  stored as `TEXT`, treated as opaque strings, never parsed for meaning
- API responses follow the OpenAPI spec in `/docs/openapi.yaml` as source of
  truth — regenerate the spec file when adding endpoints, don't let it drift
- Every new BSP/platform adapter needs: (1) the adapter class, (2) a fixture-
  based unit test using recorded sample responses, (3) an entry in the
  `platform_connections.provider` enum documented in `shared/models/`
- Segment-level unit economics (churn, CAC, ACV) differ by business category
  — never build a feature or report that blends F&B/salon/clinic/retail into
  one number. Keep them queryable separately (see `cohort_retention` view).

## Slash Commands Available

See `.claude/commands/` — custom commands for repeated workflows:
- `/new-bsp-adapter <name>` — scaffolds a new WhatsApp BSP adapter matching
  the existing interface + test fixture pattern
- `/cohort-report` — runs the cohort retention query and summarizes by segment
- `/attribution-signal-check` — audits signal_completeness_pct across active
  businesses, flags anything below threshold

## What NOT to Build Right Now (explicit — prevents scope creep)

Per the diligence memo's Session 6 recommendation — do not build these without
an explicit override conversation, even if a feature request seems to imply
them:
- Commission-based revenue / payment-flow sitting (RBI PA/PG compliance
  surface pre-PMF — see PAYMENTS.md)
- Loyalty network / cross-promotion between businesses (see OFFERS.md —
  requires the same consumer-side density gate as marketplace, below)
- Franchise tooling
- Full multi-touch attribution (v0 is proxy-signal correlation only)
- API/integration layer for third parties (premature — no partner demand yet)

### Decision log

**2026-07-04 — Marketplace / consumer discovery app: spec'd, build gated.**
Ganesh reviewed the cross-doc rationale for deferring this (BUSINESS_VISION,
BUSINESS_MODEL, COMPETITOR_ANALYSIS, PRD non-goals, CUSTOMER/OFFERS/SEARCH/
HYPERLOCAL_ENGINE module docs all independently named and rejected it) and
approved adding it to the roadmap as a third product surface (End Consumer,
alongside SMB Owner and Agency Account Manager). Decision: **spec now, build
gated** — `USER_PERSONAS.md`, `06_MODULES/CUSTOMER.md`, and
`06_MODULES/HYPERLOCAL_ENGINE.md` now carry a real spec, and
`01_BUSINESS/ROADMAP.md` has a Phase 2.5 slot for it — but Phase 1 MVP
engineering stays 100% on existing scope, and Hyperlocal Engine build work
does not start until the trigger already defined in that doc fires: real
Phase 2 pilot data showing consumer-side density. `BUSINESS_MODEL.md`, the
PRD non-goals section, `FEATURE_LIST.md`, and `COMPETITOR_ANALYSIS.md` still
describe the pre-2026-07-04 no-marketplace position and haven't been rewritten
yet — treat this entry as superseding them on the *concept* (marketplace is
now planned, not rejected) until someone does a full consistency pass across
those four docs too.

## Who to Ask

Ganesh Patil — Founder/Architect. Owns attribution-engine and sync-engine
architecture decisions directly (per diligence memo — this is the
non-delegable moat). Backend/frontend implementation can be delegated to
Claude Code sessions or contractors, but architecture changes to the 5
principles above need explicit sign-off, not silent drift.
