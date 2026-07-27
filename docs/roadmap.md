# Three-Month Roadmap

The MVP is a deliberately scoped, well-grounded foundation. The path to production:

## Headline next capabilities

Three investments that turn the MVP from a single-page advisor into a durable, revenue-aware,
self-improving system:

### 1. Live upselling & cross-sell recommendations
Beyond evaluating one page, recommend what to sell *with* it. A new **`recommend` capability**
that, grounded in the live Healf catalogue:
- suggests **complementary products** ("pairs well with…") using product type, tags, benefits, and
  goal metafields (e.g. Electrolytes → recovery, sleep, hydration bottles);
- pushes the **subscription upsell** with the real saving already extracted (e.g. "subscribe and
  save 10%"), and proposes **bundles** ("variety pack + shaker");
- answers merchandising questions ("what should we cross-sell on this PDP?") with ranked,
  evidence-backed picks — never invented SKUs, always real catalogue items with links.
Data source: extend the benchmark crawler into a lightweight **catalogue index** (handle, type,
tags, price, benefits) so recommendations are grounded, not hallucinated.

### 2. Proper database storage & persistence
Replace the in-memory session store and product cache (which reset on restart) with durable storage:
- **Postgres** for sessions, conversation history, product **snapshots** (so answers are
  reproducible and diffable over time), and evaluation history per product;
- **Redis** for the hot product cache and rate limiting;
- **object storage** for raw page snapshots (audit trail / regression fixtures).
This unlocks catalogue-wide audits, "what changed since last week?" comparisons, and multi-user
history — none of which the ephemeral MVP can do.

### 3. Self-improving loop
Close the feedback loop so the agent gets better with use:
- **capture signals** — thumbs up/down on answers, which recommendations were *applied* to a
  listing, and whether applied changes moved reviews/conversion;
- **build an eval dataset** from those signals + human corrections;
- **auto-tune** the evaluation rubric weights and prompts against the dataset, and **A/B test**
  generated content variants;
- **continuously refresh the site benchmark** from the crawler so "what good looks like" tracks the
  catalogue as it evolves.
Guardrail: all tuning is offline-evaluated before rollout, and grounding rules (no invented facts,
no medical claims) are never learned away.

---

## The phased plan

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
