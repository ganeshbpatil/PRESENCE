# Git Standards

- Trunk-based development on `main`, feature branches for anything non-trivial
- Commit messages: conventional commits style (`feat:`, `fix:`, `refactor:`, `docs:`) — keeps the changelog and eventual release notes generation clean
- No direct pushes to `main` once a second contributor joins — PR review required, matching the graduated rigor model (Phase 0–1 solo founder can push directly; Phase 2+ with a hire, require review)
- CI gate (see 07_TESTING/TESTING_STRATEGY.md): attribution-engine and billing test suites must pass at 100% before merge — everything else is a warning, not yet a hard block, at this phase
