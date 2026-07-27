# Roadmap

The MVP is read-only with in-memory state. This is how it grows into something durable,
revenue-aware, and self-improving. Read the three priorities first; the phasing and production notes
follow.

## The three priorities

### 1. Upsell and cross-sell

Today it evaluates one page in isolation. The obvious next capability is recommending what to sell
*with* a product.

- **What:** complementary items ("pairs well with"), the subscription upsell using the saving it
  already extracts, and bundles.
- **How it stays grounded:** build a lightweight catalogue index (handle, type, tags, price,
  benefits) off the same crawler that feeds the benchmark, so every suggestion is a real SKU with a
  link, never invented.
- **Why it matters:** this is the most directly revenue-relevant thing the agent could do for a
  merchandising team.

### 2. Real persistence

Sessions and the product cache currently live in memory and vanish on restart; sidebar history is
just localStorage.

- **Postgres** for sessions, conversation history, and product *snapshots* (snapshots make answers
  reproducible and let you diff a page over time: "what changed since last week?").
- **Redis** for the hot cache and rate limiting.
- **Object storage** for raw page snapshots that double as regression fixtures.
- **Unlocks:** catalogue-wide audits and multiple users, neither of which the ephemeral MVP can do.

### 3. A feedback loop

The agent should get better as people use it.

- **Capture:** thumbs up/down, which recommendations actually got applied to a listing, and whether
  those changes moved reviews or conversion.
- **Learn:** turn that into an eval set, then tune the rubric weights and prompts against real
  outcomes and A/B test generated copy.
- **Guardrail:** tuning happens offline before rollout, and the grounding rules (no invented facts,
  no medical claims) are never optimised away.

## Three-month phasing

**Month 1: Reliability.** Move state to Postgres/Redis. Add an **extraction regression suite** that
snapshots known Healf pages and asserts the parsed fields (the headless flight-data format is the
thing most likely to break quietly when the site changes). Turn the on-demand benchmark into a
background crawler, add real review-provider adapters (Okendo/Yotpo) for full review text, and add
observability for extraction success rates per source.

**Month 2: Multimodal.** Remove the current blind spots: vision over product images (hero vs
lifestyle vs nutrition label, quality and duplicate checks), OCR on nutrition labels for actual
quantities, alt-text generation for images that lack it, and review sentiment and topics.

**Month 3: Acting on findings.** Where it stops being an advisor and starts acting: writing drafts
back to Shopify Admin behind a human approval step with version history, scheduled catalogue audits
with alerts on regressions, team workspaces, and a launch-readiness check that gates a listing before
it goes live.

## Production hardening (throughout)

- Auth, rate limiting, audit logs, secret rotation.
- Model fallback, prompt/schema versioning, and an eval dataset.
- Content moderation and health-claim review, which matters more than usual for a supplements
  marketplace.
- Raw-page snapshot storage for reproducibility.
- Browser automation kept strictly as a fallback for the rare field plain HTTP can't reach, never
  the default.
