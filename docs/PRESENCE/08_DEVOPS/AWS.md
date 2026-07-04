# AWS — Decision Record: NOT ADOPTED (documented, not deleted)

An earlier draft specified AWS as the deployment target (alongside NestJS/Prisma/Clerk). This was explicitly reviewed and rejected in favor of the existing Hostinger VPS setup — see `00_PROJECT_OVERVIEW/PROJECT_OVERVIEW.md` Decision 1 and `03_ARCHITECTURE/SYSTEM_ARCHITECTURE.md` for the full trade-off table.

**Rationale for rejection:** AWS managed services (RDS, ALB, etc.) would raise the marginal infra cost baseline the Session 4/5 financial model assumes is near-zero (given existing VPS is already paid for and running comparable workloads for AgencyOS/skyiDM). No stated reason existed to prefer AWS over the existing setup at this stage.

**When to revisit:** Phase 4+ (Series A readiness) is the natural re-evaluation point — if/when VPS capacity, reliability requirements, or team-scaling needs (multiple engineers needing managed infra rather than VPS SSH access) justify the added cost and migration effort, revisit this decision explicitly. Do not silently drift toward AWS services module-by-module before then (e.g., don't reach for S3/R2 for a storage need without checking this decision record first — self-hosted MinIO or the VPS's own disk is the default unless there's a specific reason).
