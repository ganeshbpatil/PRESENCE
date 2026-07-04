# Module: Analytics (Attribution Engine) — **P0 — THE MOAT**

Isolated service (`services/attribution-engine/`), not embedded in sync-engine — deliberately, so it can be extracted/licensed independently later. v0 scope: proxy-signal correlation only (GBP direction-requests, call-tracking, WhatsApp-campaign-to-inbound correlation with a 7-day lag window). Explicitly NOT in v0: full multi-touch attribution modeling — that's a Year 2+ ambition once data volume justifies it. `signal_completeness_pct` tracked per business as a product-quality leading indicator, not a vanity metric.
