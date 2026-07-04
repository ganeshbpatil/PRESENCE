# Component Library

Inherits from AgencyOS's existing shadcn/ui-based component set. Net-new components specific to PRESENCE:

- `AttributionSummaryCard` — the single-headline-number component for the attribution dashboard
- `PlatformHealthBadge` — visual indicator for `platform_connections.sync_status` (healthy/degraded/broken) — this is the trust-signal UI element referenced in the architecture docs
- `ClientSwitcher` — agency console's one-click multi-tenant switcher
- `CreditBalanceIndicator` — shows AI/WhatsApp credit balance + low-balance warning, ties to `credit_ledger`
- `TemplateMessageComposer` — template-first WhatsApp campaign builder component

Build these as part of Phase 1 frontend work, not before — no component library investment ahead of real screens needing them.
