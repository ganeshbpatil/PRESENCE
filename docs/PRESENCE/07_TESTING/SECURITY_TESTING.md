# Security Testing

## Phase 1 (mandatory now, not deferred)
- Webhook signature verification tested explicitly (see QA_CHECKLIST.md)
- No secrets in code/logs — grep-based CI check for common credential patterns
- RBAC role boundaries tested (Agency Viewer cannot access write endpoints, one agency cannot access another agency's businesses)

## Phase 3+ (formal discipline)
Penetration testing, formal security audit, OWASP Top 10 systematic review — appropriate once there's real customer data volume and revenue at stake justifying the cost, per the phased rigor model in TESTING_STRATEGY.md.
