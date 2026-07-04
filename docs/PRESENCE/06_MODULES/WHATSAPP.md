# Module: WhatsApp — **P0 — highest-priority module, the core daily-use loop**

See `services/sync-engine/adapters/whatsapp/base.py` for the BSP abstraction contract and `gallabox.py` for the primary adapter implementation. Scope: review-request triggers (post-visit), drip sequences, credit-metered broadcast, real-time delivery-status tracking via webhook. Cost-optimization logic (route to free service-window sends wherever possible vs. paid template sends) is a P0 requirement, not a nice-to-have — directly protects gross margin per the sourced WhatsApp pricing research.
