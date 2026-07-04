# Backend Standards

- Async-first: all I/O-bound routes (DB, external API calls) use `async def` + async SQLAlchemy session
- Celery tasks for anything that shouldn't block the request/response cycle — see EVENT_ARCHITECTURE.md for what's sync vs. async
- Every new BSP/platform adapter needs: (1) the adapter class implementing the abstract interface, (2) a fixture-based unit test using recorded sample responses, (3) a documented entry in the `platform_connections.provider` enum
- Config via environment variables (`.env` locally, real secrets manager in production per SECURITY_ARCHITECTURE.md) — never hardcoded credentials, ever, including "just for testing"
