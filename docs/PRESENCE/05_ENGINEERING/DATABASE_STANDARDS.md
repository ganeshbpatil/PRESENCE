# Database Standards

- All schema changes via Alembic migrations generated from SQLAlchemy model changes — never hand-edit the DB schema directly, even in dev
- Every migration reviewed for: does it touch `credit_ledger` (append-only rule), does it touch `businesses.churned_at` (cohort-tracking rule), does it introduce a blended-segment table (forbidden)
- Indexes added deliberately, not reactively — `businesses(category, tier)` and `businesses(churned_at)` exist from day 1 because cohort/retention queries are a known, frequent access pattern, not an afterthought
