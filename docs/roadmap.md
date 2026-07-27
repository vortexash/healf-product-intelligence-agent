# Where this goes next

The MVP is a read-only, single-page advisor with in-memory state. Here's how I'd grow it, starting
with the three things I think matter most.

## The three big ones

**Upsell and cross-sell.** Today it looks at one page in isolation. The obvious next capability is
recommending what to sell alongside a product - complementary items ("pairs well with"), the
subscription upsell using the saving it already extracts, and bundles. The trick is keeping it
grounded: I'd build a lightweight catalogue index (handle, type, tags, price, benefits, goal
metafields) off the same crawler that feeds the benchmark, so every suggestion is a real SKU with a
link, not something the model made up. This is also the most directly revenue-relevant thing the
agent could do for a merchandising team.

**Real persistence.** Right now sessions and the product cache live in memory and vanish on restart,
and the sidebar's chat history is just localStorage. I'd move to Postgres for sessions, conversation
history, and product snapshots - snapshots matter because they make answers reproducible and let you
diff a page over time ("what changed since last week?"). Redis for the hot cache and rate limiting,
and object storage for raw page snapshots that double as regression fixtures. This is also the
foundation for catalogue-wide audits and multiple users.

**A feedback loop.** The agent should get better as people use it. Capture the signals - thumbs
up/down on answers, which recommendations actually got applied to a listing, and whether those
changes moved reviews or conversion - and turn them into an eval set. From there you can tune the
rubric weights and prompts against real outcomes and A/B test generated copy, while continuously
refreshing the benchmark so "what good looks like" tracks the catalogue as it changes. The one rule
I'd hold firm: tuning happens offline before rollout, and the grounding rules (no invented facts, no
medical claims) never get optimised away.

## Roughly how I'd phase it

Month 1 is reliability. Move state to Postgres and Redis, and - more importantly - add an extraction
regression suite that snapshots known Healf pages and asserts the parsed fields, because the headless
flight-data format is the thing most likely to break quietly when the site changes. Turn the
on-demand benchmark sampling into a background crawler, add proper review-provider adapters
(Okendo/Yotpo etc.) for individual review text, and put in observability so I can see extraction
success rates per source.

Month 2 is the multimodal stuff that removes the current blind spots: vision over product images
(hero vs lifestyle vs nutrition-label, quality and duplicate checks), OCR on nutrition labels to get
actual quantities rather than just the ingredient list, alt-text generation for the images that are
missing it, and review sentiment/topics.

Month 3 is where it stops being an advisor and starts acting: writing drafts back to Shopify Admin
behind a human approval step with version history, scheduled catalogue audits with alerts on
regressions, team workspaces, and a launch-readiness check that gates a listing before it goes live.

## Production hardening (throughout)

Auth, rate limiting, audit logs, secret rotation. Model fallback and prompt/schema versioning.
Content moderation and health-claim review, which matters more than usual for a supplements
marketplace. Raw-page snapshot storage for reproducibility. And browser automation kept strictly as
a fallback for the rare field that plain HTTP genuinely can't reach - not the default.
