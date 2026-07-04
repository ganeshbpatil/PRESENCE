# CI/CD

GitHub Actions → VPS deployment (SSH/Docker context, or a lightweight GitOps approach if repo count across the founder's ventures continues to grow — worth evaluating once PRESENCE is the 3rd+ project on this pattern).

```yaml
on: [push to main]
jobs:
  test:   # Testing Strategy's phase-appropriate gate — attribution-engine
          # and billing suites are a hard block; everything else a warning
          # at Phase 1 (see 07_TESTING/TESTING_STRATEGY.md)
  build:  # Docker image build, tag with commit SHA
  deploy:
    - staging: automatic on merge to main
    - production: manual approval gate (founder) — this handles customer-
      facing billing and platform credentials, not a rubber-stamp step
```
