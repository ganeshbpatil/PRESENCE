# Frontend Standards

- Next.js 15, TypeScript strict mode, Tailwind, shadcn/ui, TanStack Query
- Typed API client generated from the OpenAPI spec — never hand-write fetch calls against endpoints that exist in the spec
- Component reuse from AgencyOS design system is the default — new components only for genuinely PRESENCE-specific UI (see 04_DESIGN/COMPONENT_LIBRARY.md)
- No client-side business logic that duplicates backend logic (e.g., don't recompute attribution scores client-side — always read the computed value from the API)
