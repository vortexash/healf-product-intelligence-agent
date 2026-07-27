# Healf Product Intelligence Agent

A chat agent for Healf product pages. Paste a product URL, ask a question in plain English, and get
an answer pulled from the live page with a source for every fact.

**Live demo:** https://healf-product-intelligence-agent.vercel.app
_(The backend runs on a free tier that sleeps when idle, so the first request takes 30-60s to wake
up, then it's fast.)_

**Jump to:** [What you can ask](#what-you-can-ask) · [Quick start](#quick-start) ·
[How it works](#how-it-works) · [API](#the-api) · [Tests](#tests) · [What's next](#whats-next) ·
[Layout](#project-layout)

Built as a take-home with a ~5-hour guideline, so it's a solid foundation rather than a finished
product. The parts worth a look are how it pulls structured data out of Healf's headless storefront,
and how it keeps facts deterministic while using the LLM only for the open-ended work.

## What you can ask

Paste a URL, then ask. Follow-ups reuse the same product, so you never repeat the URL.

**Factual**: answered straight from the page (no LLM), always with sources:

- Does this contain Vitamin D?
- What are the ingredients?
- How many reviews does it have, and what's the rating?
- What's the price on subscription vs one-time?
- Is it in stock?

**Evaluate the listing**: a deterministic score, then the LLM prioritises the fixes:

- What can I improve on this page?
- Are the images good enough?
- How is the SEO?

**Generate content**: grounded only in the page's actual facts:

- Rewrite the product description.
- Write an FAQ for this product.

Every answer shows the sources it used, and an evidence drawer lets you see the exact field, excerpt,
and confidence behind each fact.

## Quick start

You need Python 3.12+ and Node 20+ (or skip both with `docker compose up --build`).

**1. Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # optional: add OPENAI_API_KEY or ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

**2. Frontend** (new terminal)

```bash
cd frontend
npm install
cp .env.example .env.local    # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev
```

Open http://localhost:3000.

Factual questions work with **no API key**. Evaluation and content generation need one: set either
`OPENAI_API_KEY` or `ANTHROPIC_API_KEY` and it auto-detects the provider.

## How it works

```
chat UI (Next.js)
  -> FastAPI: validate URL + SSRF check -> fetch the live page
  -> parsers -> merge into one ProductData (every field keeps its source)
  -> route the question -> deterministic answer, or rules + LLM
  -> stream back over SSE (status -> product -> tokens -> done)
```

Three things worth calling out:

**Getting data out of Healf.** Healf runs on Shopify but through a headless Next.js frontend, so the
obvious `/products/{handle}.json` just returns HTML. The real data lives in three places and it
parses all of them: the Shopify product object embedded in React Server Component payloads
(`self.__next_f.push(...)`) for variants/pricing/subscriptions/images, a JSON-LD block for reviews
and rating, and Radix accordions in the HTML for description/ingredients/usage. A merger combines
them by a precedence order and keeps evidence for every field, which is what the evidence drawer
shows.

**Deterministic vs LLM.** Facts (ingredients, price, reviews, availability) come straight from the
parsed data, so the LLM can't invent them. The LLM only does open-ended work (evaluation narrative,
summaries, rewrites), and it only ever sees a trimmed dict of facts, never raw HTML. Ingredient
answers even distinguish "not listed on the page" from "doesn't contain it", since those aren't the
same claim.

**Site context.** `scripts/build_benchmark.py` samples a handful of live products into a benchmark
(median description length, image count, alt-text coverage, and so on), so evaluation can say "add
one more image to match comparable pages" instead of a generic tip. Without it, evaluation stays
product-specific and says so.

More detail and diagrams are in [docs/architecture.md](docs/architecture.md) and
[docs/diagrams.md](docs/DIAGRAMS.md).

## The API

Four endpoints: `GET /health`, `POST /api/products/fetch`, `POST /api/chat`, and
`POST /api/chat/stream` (SSE: `status` -> `product` -> `token` -> `complete`).

```bash
curl -X POST localhost:8000/api/chat -H 'content-type: application/json' \
  -d '{"message":"https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack\nDoes it contain Vitamin D?"}'
```

## Tests

```bash
cd backend && pytest -q       # 68 tests: URL/SSRF, parsers, merger, factual answers, evaluation, API
cd frontend && npm test       # component tests
```

Parser tests run against a saved real Healf page so they don't need the network; the API tests mock
the fetch and the LLM. Real captured responses are in
[examples/example_outputs.md](examples/example_outputs.md) if you want to see output without running
anything.

## What's next

The MVP is deliberately read-only with in-memory state. The three things I'd build next:

1. **Upsell / cross-sell**: recommend what to sell alongside a product (complementary items, the
   subscription upsell, bundles), grounded in a catalogue index so the SKUs are real.
2. **Real persistence**: Postgres for sessions, history, and product snapshots (so answers are
   reproducible and you can diff a page over time), Redis for caching and rate limits.
3. **A feedback loop**: capture which recommendations get applied and their impact, and tune the
   rubric and prompts against real outcomes.

The full plan, three-month phasing, and production hardening are in [docs/roadmap.md](docs/roadmap.md).

## What it doesn't do yet

- No vision: it doesn't inspect image content, and it reads the ingredient list but not nutrient quantities.
- Reviews are aggregate only (count and rating); individual review text isn't pulled in.
- State is in-memory, so it resets on restart. Recent chats in the sidebar are stored in the browser.
- Extraction depends on Healf's current markup, so a regression suite over saved pages is the first
  thing I'd add for production.

## Project layout

```
backend/app/
  navigation/     URL parsing, SSRF validation, the live fetch client
  ingestion/      the six parsers + the merger
  intelligence/   intent routing, factual answers, evaluation, LLM writer, response composer
  context/        in-memory sessions/cache, benchmark loader
frontend/
  components/     chat/, product/, intelligence/, ui/
  lib/            SSE client, types, helpers
docs/             architecture, roadmap, diagrams
examples/         real captured outputs
```

Stack: FastAPI + httpx + BeautifulSoup/lxml + Pydantic v2 on the backend; Next.js (App Router) +
TypeScript + Tailwind on the frontend.
