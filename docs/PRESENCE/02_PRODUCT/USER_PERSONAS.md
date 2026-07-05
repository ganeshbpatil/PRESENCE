# User Personas

> **2026-07-04:** Expanded from the original "2 max" cap to 3, per Ganesh's
> explicit approval to spec a Customer/Marketplace product surface (see
> `CLAUDE.md` decision log and `06_MODULES/HYPERLOCAL_ENGINE.md`). Persona C
> below is a **spec-only, future persona** — there is no consumer-facing
> product to design or build against it yet. Do not build onboarding flows,
> auth, or UI for Persona C until the Hyperlocal Engine build-gate trigger
> fires (real Phase 2 pilot data showing consumer-side density). Personas A
> and B are unchanged and remain the only personas with an active product.

## Persona A: SMB Owner (Salon/Spa/Gym)
- Owner-operator, single or 2-location, Pune Tier-1 area (Baner/Koregaon Park pilot zones)
- Currently: fragmented presence across GBP/WhatsApp/Instagram, managed ad hoc (owner's relative, ₹5–8K/mo freelancer, or nobody)
- Decision-making: fast, owner-led, single decision-maker — days not months if trust established
- Highest WTP signal: has tried and abandoned a paid tool/agency retainer before (churned-but-aware segment) — targets messaging around "tried an agency, it didn't work"
- Jobs-to-be-done: "I need to know if responding to reviews and running WhatsApp campaigns is actually bringing in customers, not just busywork"

## Persona B: Agency Account Manager
- Manages 20–50 SMB client accounts across a digital agency's book
- Currently: stitches together Zoho + manual reporting per client, no unified console
- Jobs-to-be-done: "I need to manage all my clients' presence + prove ROI to them without building custom tooling per client"
- Success metric: client retention (their client's churn is their churn) and time-to-report (manual reporting is the biggest time sink today)

## Persona C: End Consumer (SPEC-ONLY — Phase 2.5+, build gated)
- Lives/works in the same Pune micro-geo as PRESENCE-managed businesses;
  discovers salons/spas/gyms/clinics/F&B/retail near them and compares
  options before visiting or booking
- Currently: relies on Google Maps/Search, Instagram, word of mouth, or
  incumbent discovery apps (Justdial/Magicpin/Nearbuy) — PRESENCE has no
  presence in this journey today
- Jobs-to-be-done: "I want to find a good, trustworthy [salon/gym/clinic]
  near me right now, see if they're actually good (not just paid placement),
  and act on it (call, WhatsApp, get directions) in one tap"
- Why this persona doesn't have a product yet: PRESENCE's reviews/ratings
  data (the raw material a discovery experience would need) only becomes
  meaningfully dense once enough PRESENCE-managed businesses exist in the
  same micro-geo — that density does not exist at Phase 0/1. Building for
  this persona before then means building a cold-start consumer app with
  no data advantage over incumbents, which is exactly the fight
  `COMPETITOR_ANALYSIS.md` marks RED. See `06_MODULES/HYPERLOCAL_ENGINE.md`
  for the actual trigger condition and spec.
- Success metric (once active): would be repeat-discovery-to-visit
  conversion rate, not signups — do not design toward vanity install/signup
  numbers when this persona's product does get built.
