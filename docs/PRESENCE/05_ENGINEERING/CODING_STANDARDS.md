# Coding Standards

## Language & Style
Python 3.11+, FastAPI, SQLAlchemy 2.0, type-hinted throughout (no untyped function signatures in new code). Ruff for linting/formatting — fast, single-tool, fits a lean team.

## Architecture Discipline (adopted from the rejected NestJS brief, applied to Python)
- Repository pattern via SQLAlchemy — no raw queries scattered in route handlers; route handlers call service functions, service functions call repositories
- Dependency injection via FastAPI's native `Depends` — no manual singleton hacks
- Clean separation: `gateway/` (routing/validation only) → `services/*/` (business logic) → `shared/models/` (data layer). Never let a route handler contain business logic directly.

## What NOT to Do
- No direct provider SDK calls outside `ai-orchestrator/router.py` or `adapters/whatsapp/*.py` — this is enforced, not a suggestion (see CLAUDE.md principles)
- No `UPDATE` on `credit_ledger.balance_after` — append-only, always
- No blended-segment queries/reports across business categories — always group by `category`
