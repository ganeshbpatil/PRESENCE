# System Architecture

## Stack Decision Record (locked — see 00_PROJECT_OVERVIEW/PROJECT_OVERVIEW.md Decision 1)

| Dimension | FastAPI/Python (CHOSEN) | NestJS/Prisma/Clerk/AWS (rejected) |
|---|---|---|
| Reuses existing infra | Yes — zero migration cost | No — parallel infra stack, new ops burden |
| Aligns with automation ecosystem (n8n, Celery, Python-first Hermes agents) | Yes | No — second primary backend language |
| Margin model validity | Holds (~₹50–100/customer/mo infra) | Breaks — AWS managed services + Clerk MAU billing raise marginal cost baseline |
| Auth | Self-built JWT+OAuth (more upfront work, zero per-user vendor cost) | Clerk — faster but compounds cost at 8-10K customer target |
| Team/talent pool | Strong Python/FastAPI pool in Pune | Comparable, not a differentiator |

**Rejected pattern-matching risk:** the NestJS/Prisma/Clerk/AWS combination reads as a generic "modern SaaS boilerplate" recommendation, not one derived from this company's actual constraints. Adopted anyway from that brief: Clean Architecture, SOLID, DDD, repository pattern, dependency injection, event-driven design where appropriate, RBAC, API-first, documentation-first, modular-monolith-with-microservice-optionality. None of these require NestJS — all map cleanly onto FastAPI (repository pattern via SQLAlchemy, DI via FastAPI's native `Depends`, modular monolith via service-folder boundaries).

## Modular Monolith Structure

```
services/
├── sync-engine/          # GBP + Meta + WhatsApp pull/push
│   └── adapters/whatsapp/  # BSP abstraction — see below
├── attribution-engine/    # THE MOAT — isolated, extractable later
├── ai-orchestrator/       # cache-first, model-agnostic AI routing
├── billing/               # subscription + metered credits, Razorpay
└── agency-console/        # multi-tenant white-label
shared/
├── models/                # SQLAlchemy — single source of truth schema
└── events/                 # Redis pub/sub internal event bus
gateway/                    # FastAPI entrypoint, behind Traefik
```

Each service folder is independent enough to become a real microservice later if/when scale justifies it (per the "future migration to microservices must always remain possible" principle) — but starts as a modular monolith because that's the right complexity level for a pre-Phase-0-validation company. Do not split into actual separate deployed services until there's a concrete operational reason (independent scaling need, independent deploy cadence need, or team-boundary need) — splitting prematurely adds ops overhead with zero benefit at this stage.

## Non-Negotiable Principles (from CLAUDE.md — repeated here since architecture docs are the source of truth)
1. GBP/Meta are sync sources, never system of record — canonical data lives in our Postgres
2. WhatsApp BSP is abstracted behind an interface (`adapters/whatsapp/base.py`) — new BSP = new adapter file, zero calling-code changes
3. Attribution engine is a separate service, not embedded in sync-engine — defensible IP, kept extractable
4. AI orchestrator is cache-first and model-agnostic — gross margin is a direct function of cache-hit rate
5. Credit ledger is append-only — never UPDATE balance directly

## Infra
Hostinger VPS (existing), Docker Compose, Traefik reverse proxy — isolated containers/Postgres instance from AgencyOS/skyiDM per the existing Pattern-A convention (separate blast radius). See `08_DEVOPS/` for full deployment detail and the explicit AWS non-adoption decision record.
