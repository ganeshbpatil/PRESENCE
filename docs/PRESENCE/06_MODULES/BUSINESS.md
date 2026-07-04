# Module: Business (Core Entity) — **P0**

The `businesses` table (see 03_ARCHITECTURE/DATABASE_ARCHITECTURE.md) is the tenant-scoped root entity. v1 category scope: `salon_spa_gym` (primary v1 persona), `clinic_healthcare`, `fnb`, `retail_fashion_jewellery` — kept narrow deliberately, not all categories sold in parallel at launch (see 02_PRODUCT/PRODUCT_REQUIREMENT_DOCUMENT.md). Tier field drives feature-gating (Starter/Growth/Scale/Agency).
