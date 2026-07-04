# Module: Notifications — **P0, minimal**

Internal notifications (new review arrived, platform connection degraded, credit balance low) via the existing Redis pub/sub event bus (see 03_ARCHITECTURE/EVENT_ARCHITECTURE.md). Delivery channels for v1: in-app + email. SMS/push notification infrastructure is a P1/P2 addition once the in-app+email baseline proves insufficient — don't build three notification channels before validating one is used.
