# Healf Product Intelligence Agent

A chat agent that answers questions about Healf product pages using live data from the site. You
paste a product URL, ask something in plain English ("does this have vitamin D?", "what's weak about
this page?", "rewrite the description"), and it fetches the page, pulls out what it needs, and
answers you — with the source for each fact, and follow-ups don't need the URL again.

Live demo: https://healf-product-intelligence-agent.vercel.app

Try:

```
https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack
Does this have Vitamin D?
```

(The backend is on Render's free tier and sleeps when idle, so the first request after a while takes
30-60s to wake up. It's quick after that.)

This was a take-home with a ~5-hour guideline, so it's built as a solid foundation rather than a
finished product. The parts I found most interesting are how it gets structured data out of Healf,
and keeping facts deterministic while using the LLM only for the open-ended stuff.

## How it works

```
chat UI (Next.js) -> FastAPI -> validate URL + SSRF check -> fetch the live page
  -> parsers -> merge into one ProductData (with evidence) -> route the question
  -> deterministic answer, or rules + LLM -> stream back over SSE
```

### Getting data out of Healf

This is the part that took the most digging. Healf runs on Shopify, but it's a headless Next.js
frontend rather than a classic Liquid theme, so the obvious move — hitting `/products/{handle}.json`
— doesn't work. Those URLs just return the app's HTML. The real product data is spread across three
places, and I parse all of them:

- The Shopify product object is embedded in the page's React Server Component payloads
  (`self.__next_f.push(...)`). That's where variants, pricing, subscription plans, images and SEO
  come from.
- A JSON-LD `Product` block carries the review count and rating.
- The description, ingredients and usage instructions live inside Radix accordions in the HTML.

Each parser returns a fragment plus evidence — which source it came from, an excerpt, a confidence.
A merger combines them using a precedence order and records any conflicts, so every field on the
final product can be traced back to where it came from (that's what the evidence drawer in the UI
shows). The old `.json` probe is still in there; it just no-ops on Healf and would work on a normal
Shopify store.

### Deterministic vs LLM

Facts don't go through the model. Ingredient lookups, reviews, price, availability, image counts —
those are answered straight from the parsed data. The LLM only handles open-ended work: page
evaluation, prioritising fixes, summaries, and writing (rewrites, FAQ, SEO). And it never sees raw
HTML, only a trimmed dict of extracted facts, so it can't invent a price or an ingredient.

Two grounding details I cared about:

- Ingredient answers distinguish present / not listed / unknown. If vitamin D isn't in the list it
  says "not listed on the live page", not "this product doesn't contain it" — those aren't the same
  claim, and the page might just be incomplete.
- The page score is a weighted heuristic, and it's labelled as one. The signals are computed in
  code; the LLM writes the narrative and ranks the recommendations on top of them.

### Site context

Evaluations are more useful when they know what "good" looks like across Healf. `scripts/build_benchmark.py`
samples a handful of live products into `backend/data/benchmark.json` — median description length,
image count, alt-text coverage, how often ingredients/reviews/subscriptions show up. The evaluator
passes that to the LLM, so a recommendation can say "add another image to match the ~4 that
comparable pages have" instead of a generic "add more images". If the file isn't there, evaluation
stays product-specific and says so rather than pretending to compare against the whole catalogue.

## Running it

Needs Python 3.12+ and Node 20+.

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # add an OpenAI or Anthropic key for evaluation/rewrites
uvicorn app.main:app --reload --port 8000
```

Frontend (another terminal):

```bash
cd frontend
npm install
cp .env.example .env.local    # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev
```

Then open http://localhost:3000. Or `docker compose up --build` to run both at once.

Factual questions work with no API key. Evaluation and content generation need one — set either
`OPENAI_API_KEY` or `ANTHROPIC_API_KEY` and it picks the provider from whichever key is present.

## The API

Four endpoints: `GET /health`, `POST /api/products/fetch`, `POST /api/chat`, and
`POST /api/chat/stream` (server-sent events: `status` -> `product` -> `token` -> `complete`).

```bash
curl -X POST localhost:8000/api/chat -H 'content-type: application/json' \
  -d '{"message":"https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack\nDoes it contain Vitamin D?"}'
```

## Tests

```bash
cd backend && pytest -q       # 68 tests: URL/SSRF, each parser, merger, factual answers, evaluation, API
cd frontend && npm test       # component tests
```

Parser tests run against a saved copy of a real Healf page (`backend/tests/fixtures/`) so they don't
depend on the network, and the API tests mock the fetch and the LLM. There's a small offline smoke
script too: `python scripts/probe_fixture.py`.

Some real responses are captured in [`examples/example_outputs.md`](examples/example_outputs.md) so
you can see output without running anything.

## What it doesn't do yet

- No vision. It doesn't look at image content, and it reads the ingredient list but not nutrient
  quantities.
- Reviews are aggregate only (count and rating). Individual review text isn't pulled in.
- State is in-memory, so sessions and the product cache reset on restart. The sidebar's recent chats
  are just localStorage.
- Extraction depends on Healf's current markup. If they change the flight-data format it'll need
  updating — a regression suite over saved pages is the first thing I'd add.

## Where I'd take it next

Three I'd prioritise:

1. Upsell / cross-sell. Right now it evaluates one page; the natural next capability is recommending
   what to sell alongside it — complementary products, the subscription upsell (with the real saving
   it already extracts), bundles — grounded in a catalogue index so the SKUs are real, not invented.
2. Real persistence. Postgres for sessions, history and product snapshots (so answers are
   reproducible and you can diff a page over time), Redis for caching and rate limits. That's also
   what makes catalogue-wide audits possible.
3. A feedback loop. Capture thumbs up/down and which recommendations actually got applied, turn that
   into an eval set, and tune the rubric weights and prompts against it — without letting the
   grounding rules get tuned away.

The longer version, plus the production hardening (auth, rate limiting, observability, content
moderation for health claims, model fallback) is in [`docs/roadmap.md`](docs/roadmap.md). There are
architecture notes and diagrams in [`docs/`](docs/).

## Layout

```
backend/app/
  navigation/     URL parsing, SSRF validation, the live fetch client
  ingestion/      the parsers + the merger
  intelligence/   intent routing, factual answers, evaluation, the LLM writer, response composer
  context/        in-memory sessions/cache, benchmark loader
frontend/
  components/     chat/, product/, intelligence/, ui/
  lib/            SSE client, types, helpers
```

Stack is FastAPI + httpx + BeautifulSoup/lxml + Pydantic v2 on the backend, and Next.js (App
Router) + TypeScript + Tailwind on the frontend. The UI primitives are hand-written rather than
pulled from a component library — there are only five of them, so it wasn't worth the dependency.
