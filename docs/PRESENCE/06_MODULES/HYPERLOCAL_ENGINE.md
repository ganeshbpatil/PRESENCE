# Module: Hyperlocal Engine (Consumer Discovery / Marketplace-Adjacent)

**Status: SPEC'D, build gated — Phase 2.5.** Not DEFERRED-and-unexamined
anymore (see `CLAUDE.md` decision log, 2026-07-04) — Ganesh reviewed the
cross-doc rationale for the original deferral and approved adding this as a
planned product surface. What changed: this doc now has a real architecture
spec to build from. What didn't change: **the build-gate trigger below is
unchanged from the original deferral, and still applies.** This remains the
module most likely to get scope-crept into active development before its
trigger condition is actually met — reread the trigger before starting any
of the work below.

## Build-gate trigger (unchanged — do not start until this fires)

Real Phase 2 pilot data showing consumer-side density: multiple
PRESENCE-managed businesses co-located in the same micro-geo (same Pune
area/pincode) with enough synced review/rating volume that a consumer
discovery surface would offer something a consumer can't already get from
Google Maps or an incumbent discovery app. Until that data exists, building
this is a cold-start consumer app with no data advantage — the exact fight
`COMPETITOR_ANALYSIS.md` marks RED and explicitly avoids.

Concretely, before writing any code here, confirm against real Phase 2
numbers:
- At least one micro-geo (area/pincode) with ≥15–20 PRESENCE-managed
  businesses across the supported categories
- Median business in that micro-geo has ≥10 synced reviews with visible
  rating spread (not all 5-star — a discovery surface needs real signal,
  not a wall of identical ratings)
- No hard requirement on absolute business count platform-wide — density
  in one micro-geo is enough to pilot the consumer surface there first

If pilot data doesn't clear this bar by the Phase 2 exit criteria in
`01_BUSINESS/ROADMAP.md`, this stays spec-only and gets revisited at the
next phase boundary, not silently started anyway.

## Architecture spec (for when the gate fires)

**What this is:** a read-only discovery layer over data PRESENCE already
owns (businesses + synced reviews), surfaced to the Persona C consumer
identity spec'd in `CUSTOMER.md` Part 2. It is explicitly NOT a two-sided
marketplace with bookings/payments/commission in v1 — see the exclusions
below.

**Service boundary:** a new `services/discovery-engine/` service, isolated
the same way `attribution-engine` is — internal API calls to `sync-engine`
and `shared/models/` are fine, but discovery-engine does not get its own
copy of business/review data; it queries the existing tables. This keeps
GBP/Meta's sync-source-not-system-of-record principle intact: the consumer
never sees data that didn't originate from a verified sync.

**Discovery query surface (v1 scope when triggered):**
- `GET /api/v1/discovery/businesses?area=&category=&query=` — filtered list
  by micro-geo + category, ranked by a simple composite of (a) average
  rating, (b) review recency, (c) `platform_connections.sync_status`
  (a business with a broken/degraded sync should not rank above one with a
  healthy one — don't let a stale cached rating outrank current reality)
- `GET /api/v1/discovery/businesses/{id}` — detail view: aggregated rating,
  review snippets, tap-to-call/WhatsApp/directions actions per `CUSTOMER.md`
- No full-text search engine, no dedicated search infrastructure, no
  geospatial index in v1 — filtered SQL queries against existing
  `businesses`/`reviews` tables with the existing `area`/`category`/
  `tier` indexes are sufficient at pilot-geo scale. Revisit only if a real
  performance problem shows up (see `SEARCH.md` — this reuses that doc's
  "simple filtered query, not a dedicated Search module" framing).

**Cross-promotion / matching logic (v1 scope when triggered, intentionally
minimal):** a business appearing in another business's "nearby, same
category tier" list is a query-time computation (same micro-geo, adjacent
category, both `sync_status = healthy`), not a stored recommendation graph.
No ranking algorithm investment beyond the composite above until real
consumer engagement data says it's warranted.

**Explicitly excluded even once the gate fires (unchanged from before,
these still need their own separate override conversation — this spec does
not approve them):**
- Bookings/reservations/appointment scheduling
- Payment collection or commission on consumer transactions (RBI PA/PG
  compliance surface — see `CLAUDE.md`'s "what not to build" list)
- Loyalty/points/cross-business coupons (`OFFERS.md`'s own separate gate)
- Consumer-authored reviews (reviews stay GBP/Meta-sourced; this surface
  reads existing reviews, it does not become a second review system)
- Paid placement/featured listings (would corrupt the rating-based ranking
  and contradicts the "reputation-to-revenue" wedge's credibility)
- Any franchise/multi-brand tooling

**Data model implications (spec only, no migration until the gate fires):**
no new tables beyond `consumers`/`consumer_saved_businesses` from
`CUSTOMER.md` Part 2 — discovery queries read existing `businesses` and
`reviews` tables directly. If query performance at real scale requires a
denormalized read model later, that's an optimization to revisit with real
load data, not a day-1 design decision.
