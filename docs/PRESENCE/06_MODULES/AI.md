# Module: AI — **P0 — the margin lever**

See `services/ai-orchestrator/router.py`. Cache-first, model-agnostic (OpenRouter primary, Anthropic direct fallback/premium path). v1 use cases: review-response drafting, WhatsApp campaign content generation, weekly insight summaries. All calls route through the orchestrator — no feature code calls a provider SDK directly. Cache-hit rate is a tracked Prometheus metric with an alert threshold (<60% hit rate flags a margin risk investigation), not just a dashboard nicety.
