# Module: Customer

Two distinct scopes live in this doc — do not conflate them:

## Part 1 — Customer Data (P0, active today)

PRESENCE does not need a full consumer-facing customer-identity system in v1
— customer data exists only as: (a) review authorship (from GBP/Meta sync,
read-only), (b) WhatsApp contact list for campaign targeting (phone number +
opt-in status + basic tags). This part is unchanged by Part 2 below — there
is still no consumer account/login system in the active build.

## Part 2 — End Consumer Product (SPEC-ONLY, Phase 2.5+, build gated)

> **2026-07-04:** Spec'd per Ganesh's approval (see `CLAUDE.md` decision log)
> to give the Hyperlocal Engine's discovery/marketplace concept a real
> customer-identity foundation to build against, once its build-gate trigger
> fires. Nothing below is built or scheduled for Phase 1. See
> `HYPERLOCAL_ENGINE.md` for the discovery/matching logic this identity layer
> feeds, and `USER_PERSONAS.md` Persona C for the target user.

**Trigger to begin building:** same as `HYPERLOCAL_ENGINE.md` — real Phase 2
pilot data showing consumer-side density (multiple PRESENCE-managed
businesses in the same micro-geo with enough review/rating volume that a
consumer discovery surface would have something incumbents don't).

**Scope once triggered:**
- Lightweight consumer identity: phone-number-based auth (OTP via the same
  WhatsApp BSP abstraction already built for business messaging — do not
  build a second messaging integration), no email/password account system
  in v1 of this surface
- Consumer profile: name, phone (opaque, never parsed), saved/favorited
  businesses, home micro-geo (pincode/area — reuse `businesses.area`'s
  existing area-ranking data, don't invent a new geo model)
- Consumer-authored actions the discovery surface needs to support:
  view a business's aggregated rating + review snippets (read-only,
  sourced from the existing `reviews` table — the consumer product is a
  new read surface on data PRESENCE already owns, not a new data source),
  tap-to-call, tap-to-WhatsApp (routes into the existing WhatsApp adapter,
  opens a service window same as any inbound message), tap-to-directions
  (external deep link, no in-house maps)
- Explicitly NOT in scope even once triggered: consumer-to-consumer
  features (follows, social graph), consumer reviews authored *through*
  PRESENCE (reviews remain GBP/Meta-sourced per the sync-source-not-
  system-of-record principle — do not let this surface become a second,
  competing review system), booking/reservation/payment collection from
  consumers (that's the commission/payment-flow item still on CLAUDE.md's
  "what not to build" list), loyalty/points (`OFFERS.md`'s own gate)

**Data model additions this implies (spec only, not migrated):** a
`consumers` table (id, phone_e164, name, home_area, created_at) and a
`consumer_saved_businesses` join table. Both would live in `shared/models/`
per the existing single-source-of-truth convention, schema-designed when
the build gate actually fires — not before, since the real usage pattern
from Phase 2 pilot data should inform the actual columns needed rather than
guessing now.

**Why phone-based auth, not Clerk/OAuth:** consistency with the project's
already-locked auth decision (self-built JWT+OTP, not a per-MAU vendor) —
a consumer product at scale is exactly the surface where per-MAU vendor
pricing would hurt most, so this follows the existing precedent rather than
introducing a new auth vendor for just this surface.
