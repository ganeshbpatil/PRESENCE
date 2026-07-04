# Database Architecture

**PostgreSQL 16**, dedicated instance isolated from AgencyOS/skyiDM prod. SQLAlchemy 2.0 models are the source of truth (`shared/models/core.py`); Alembic migrations are generated FROM the models, never hand-written independently.

## Core Tables (see shared/models/core.py for full DDL)
- `agencies` — white-label tenant root, branding config, revenue-share %
- `businesses` — tenant-scoped SMB records; `churned_at` nullable-until-churned feeds cohort tracking (non-negotiable, per the diligence memo's #1 unvalidated-variable flag)
- `platform_connections` — GBP/Meta/WhatsApp sync state; `sync_status` feeds the customer-facing platform-health dashboard (turns platform-dependency risk into a trust signal)
- `reviews` — OUR canonical review data, synced from platforms (never the reverse)
- `attribution_signals` / `attribution_correlations` — the attribution engine's input/output tables, isolated schema-wise from sync-engine tables even though same physical DB in Phase 1
- `credit_ledger` — append-only, billing-adjacent, zero tolerance for race conditions

## Design Rules (enforced, not suggested)
- Money: `NUMERIC`, never `FLOAT` — this is a billing system
- Timestamps: `TIMESTAMPTZ`, UTC, no naive datetimes anywhere
- External platform IDs: `TEXT`, opaque, never parsed for meaning
- Segment-level data (churn, CAC, ACV) never blended across categories in any view/report — `cohort_retention` materialized view groups by `category, tier` explicitly

## Multi-Tenancy Model
Schema-per-agency for white-label tenants (not row-level isolation alone) — agency white-label needs real data isolation for enterprise-trust reasons, and clinics carry health-adjacent data sensitivity that makes row-level-only isolation a heavier risk than the added migration complexity (managed via Alembic schema templating) justifies skipping.

## Cohort Tracking (non-negotiable per Session 4.5's flagged risk)
```sql
CREATE MATERIALIZED VIEW cohort_retention AS
SELECT date_trunc('month', created_at) AS cohort_month, category, tier,
    COUNT(*) FILTER (WHERE churned_at IS NULL) AS retained, COUNT(*) AS total,
    ROUND(COUNT(*) FILTER (WHERE churned_at IS NULL)::numeric / COUNT(*), 3) AS retention_rate
FROM businesses GROUP BY 1, 2, 3;
```
This must be queryable from week 1 of Phase 2 pilot — not bolted on in month 6. Churn is the single largest unvalidated variable in the entire business model.
