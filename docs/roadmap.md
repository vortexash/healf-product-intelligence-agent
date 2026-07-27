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

## More features worth building

Grouped by who they help.

### Shopping and transactions

- **Buy from the chat.** The agent already extracts the variant, selling plan, price and stock, so it
  can offer "add to basket", "buy now", or "subscribe and save" inline. To stay safe it hands off to
  Healf's real checkout with the right `variant` and `selling_plan` pre-filled, rather than handling
  cards itself, so no payment data ever touches the agent.
- **Basket-level view.** Build a basket in the chat and get a combined view: total, subscription
  savings across items, and flags for duplicated actives or things that pair badly.
- **Price and stock alerts.** Notify when a product drops in price, comes back in stock, or its
  listing quality regresses.

### Human in the loop

- **Ask a Healf expert.** When a question can't be answered from the page, is low-confidence, or is
  health-sensitive, escalate to a human (a Healf nutritionist or the curation team) instead of
  guessing. Their answer comes back into the chat and is captured so the agent learns the gap.
- **Human enrichment.** The agent flags what it couldn't extract (missing nutrient amounts,
  certifications, allergen info); a human fills those in once, and every future answer for that
  product uses it.
- **Review before publish.** Any AI-generated copy (rewrites, FAQs, SEO) goes through a human
  approval step with version history before it's written back to the store.

### Shopper-facing intelligence

- **Goal-based recommendations.** Healf tags products by goal (sleep, energy, endurance). "I want
  better sleep, is this right for me?" can recommend and compare products for a goal, with clear
  non-medical framing and an expert hand-off for anything clinical.
- **Compare products.** "How does this compare to X?" side by side on price, ingredients, reviews,
  and value.
- **Allergen and diet intelligence.** Surface allergens and diet tags (vegan, gluten-free,
  sugar-free) and answer "is this vegan?" directly.
- **Review insight.** Once full review text is ingested, summarise what people love and complain
  about, with sentiment and topics.

### Merchandiser tools

- **Bulk audits.** Paste many URLs (or a whole collection) and get a ranked list of the weakest
  listings and why.
- **Brand consistency.** Check a brand's listings against each other and against Healf's house
  standards.
- **Shareable reports.** Export an evaluation as a link or PDF for the content team, and post
  regressions to Slack.

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
