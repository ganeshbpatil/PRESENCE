# Monitoring

Self-hosted Grafana + Prometheus (already a common pattern in Docker-based stacks like this one) over paid SaaS observability at this stage — cost discipline matters pre-revenue. AWS-adjacent observability tooling (CloudWatch, etc.) is out per the AWS non-adoption decision.

## Signals to Track From Day 1
| Signal | Alert Threshold |
|---|---|
| Platform sync health (GBP/Meta/WA) | >5% of connections degraded → alert |
| AI orchestrator cache hit rate | <60% → margin risk, investigate |
| Credit ledger balance anomalies | Any negative balance → immediate alert (billing bug) |
| Cohort retention (weekly) | Any cohort dropping below the churn threshold in BUSINESS_MODEL.md → strategic review |
| API p95 latency | AI drafting >8s, sync >15min → breaches PRD NFRs |
