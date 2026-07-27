# Three-Month Roadmap

The MVP is a deliberately scoped, well-grounded foundation. The path to production:

## Month 1 — Reliability & scale

- Replace in-memory sessions/cache with **Postgres + Redis**.
- **Extraction regression suite**: snapshot known Healf pages, assert parsed fields (guards
  against site markup changes — the headless flight format can shift).
- Background **catalogue crawler** + retry queue to build the site benchmark continuously
  (the MVP samples on demand; production should sample the whole catalogue nightly).
- Per-provider **review adapters** (e.g. Okendo/Yotpo) for individual review text + sentiment.
- Observability: structured logs, request tracing, extraction success metrics per source.
- Admin-configurable evaluation rubric (weights, thresholds).

## Month 2 — Multimodal intelligence

- **Vision** analysis of product images: role classification (hero / lifestyle / nutrition
  label), quality checks, duplicate detection — removes the current "image content not
  inspected" limitation.
- **Nutrition-label OCR** to extract per-nutrient quantities (today only the ingredient list
  is captured, not amounts).
- **Alt-text generation** for images missing it (a top recommendation the tool already flags).
- Review **sentiment & topic** extraction to power richer evaluation.
- Brand-style consistency checks across a brand's listings.

## Month 3 — Operational integration

- **Shopify Admin** integration: turn generated drafts into real product-page updates.
- **Human approval workflow** + version history before anything is published.
- Scheduled **catalogue audits** with Slack/email alerts on regressions.
- Team workspaces, saved evaluations, and A/B content suggestions.
- Product-launch **readiness checks** (a gate before a listing goes live).

## Production hardening (cross-cutting)

- Rate limiting, auth, audit logs, secret rotation.
- LLM model fallback + prompt/schema versioning + eval datasets.
- Content moderation / health-claim review (regulatory sensitivity for supplements).
- Snapshot storage of raw pages for reproducibility.
- Browser automation only as a **controlled fallback** when HTTP retrieval genuinely can't
  reach a field.
