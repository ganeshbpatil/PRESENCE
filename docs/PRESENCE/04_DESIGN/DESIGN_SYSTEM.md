# Design System

**Decision:** Reuse the existing AgencyOS Next.js 15 design system/component library rather than establishing a new one for PRESENCE. Rationale: consistency across the venture portfolio reduces long-term maintenance; agency-console users may also touch AgencyOS, giving them a familiar mental model rather than a jarring UI switch between tools from the same founder's ecosystem.

Stack: Next.js 15, Tailwind, shadcn/ui, TanStack Query for server state (not Redux — this app is API-data-heavy, not client-state-heavy).

Full token/component spec: inherit from AgencyOS's existing design system doc — do not fork a parallel spec. Extend only where PRESENCE has genuinely novel UI needs (attribution dashboard visualizations, agency multi-client switcher) — see COMPONENT_LIBRARY.md.
