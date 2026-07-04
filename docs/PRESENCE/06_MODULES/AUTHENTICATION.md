# Module: Authentication — **P0**

Self-built JWT + OAuth (not Clerk — see 03_ARCHITECTURE/SYSTEM_ARCHITECTURE.md stack decision). RBAC roles: SMB Owner, Agency Admin, Agency Viewer (v1 minimum set). OAuth flows needed: GBP connect, Meta connect, WhatsApp BSP connect (Gallabox) — these are platform-connection auth flows, distinct from PRESENCE's own user-login auth.
