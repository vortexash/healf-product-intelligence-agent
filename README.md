# Healf Product Intelligence Agent

A chat-first, live product-intelligence agent for [healf.com](https://healf.com). Paste a
public Healf product URL, ask a natural-language question, and get an **evidence-grounded**
answer drawn from the live product page — then keep asking follow-ups without re-pasting the URL.

It answers **factual** questions deterministically (reviews, ingredients, price, subscription,
availability, images), **evaluates** page quality with a weighted heuristic scorecard + an LLM,
and **generates** improved content (rewrites, FAQs, SEO) — always showing its evidence and limits.

> **Not a form dashboard — a specialized ChatGPT for Healf product pages.**

---

## 1. What it does (assignment capabilities)

| Capability | Implementation |
|---|---|
| **Navigate** | Strict Healf URL validation + SSRF-safe fetch (`backend/app/navigation/`) |
| **Ingest** | Layered parsers → normalized `ProductData` with per-field evidence (`backend/app/ingestion/`) |
| **Evaluate** | Deterministic signals + weighted scorecard, refined by an LLM (`backend/app/intelligence/evaluation_rules.py`, `evaluator.py`) |
| **Act** | Factual answers, recommendations, and content generation (`factual_answerer.py`, `content_generator.py`, `response_composer.py`) |

## 2. Assignment requirement mapping

| Requirement | Where |
|---|---|
| Natural-language chat agent | `frontend/components/chat/` |
| URL in first message, auto-extracted | `url_parser.extract_url` + `chat_service.pipeline` |
| Live Healf data only (no static dataset) | `healf_client.fetch` + `ingestion/` |
| ≥ two of text/reviews/images | All three: text, review summary, images |
| Navigate / Ingest / Evaluate / Act | See table above |
| ≥ one LLM capability | Evaluation narrative + content generation |
| Evidence shown | Evidence drawer + `SourceEvidence` on every field |
| Follow-ups without URL | In-memory session product context |
| Example outputs | [`examples/example_outputs.md`](examples/example_outputs.md) (captured live) |
| README + architecture + limitations + roadmap | This file + [`docs/`](docs/) |
| Tests (mocked, not live-only) | `backend/tests/`, `frontend/test/` |

## 3. Screenshots

Live UI screenshots go in [`examples/screenshots/`](examples/screenshots/) — see the capture
guide there. The **real text** of every demo response is in
[`examples/example_outputs.md`](examples/example_outputs.md) so outputs are verifiable without
running the app.

## 4. Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full diagram and the reasoning
behind Healf's bespoke ingestion. In short:

```
User (Next.js chat) → FastAPI → URL validate + SSRF → live fetch (httpx)
   → parsers [embedded flight JSON · JSON-LD · HTML accordions · images · reviews · Shopify probe]
   → merger (precedence + evidence) → ProductData
   → intent router → { deterministic answerer | rules + LLM } → composer → SSE stream
```

**Key discovery:** Healf is a **headless Next.js** storefront, so the classic Shopify
`/products/{handle}.js|.json` endpoints return HTML, not JSON. The rich product data lives in
React Server Component **flight payloads** (`self.__next_f.push(...)`); reviews/rating come from
a JSON-LD `Product` block; and description/ingredients/suggested-use live in Radix **accordions**.
The parsers target all three; the `.js`/`.json` probe is kept for real Shopify themes and
degrades to nothing on Healf.

## 5. Technology choices

- **Backend:** FastAPI · httpx · BeautifulSoup4/lxml · Pydantic v2 · tenacity · Anthropic/OpenAI SDK · pytest/respx.
- **Frontend:** Next.js (App Router) · TypeScript · Tailwind · React Markdown · Lucide · Zod · fetch streaming (SSE).
- **State:** in-memory sessions (60 min) + product cache (10 min). No DB / vector store / auth (MVP scope).
- **shadcn/ui note:** rather than run the shadcn CLI, the ~5 primitives actually used (button, card,
  badge, textarea, drawer) are hand-written in `frontend/components/ui/` — same clean look, no CLI/network dependency.

## 6. Setup

Prerequisites: **Python 3.12+**, **Node 20+**. (Docker optional.)

```bash
git clone <repo> && cd healf-product-intelligence

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # optionally add an LLM key (see §7)

# Frontend (new terminal)
cd frontend
npm install
cp .env.example .env.local  # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## 7. Environment variables

**Backend (`backend/.env`):** factual answers work with **no key**. Set one provider to enable
evaluation narrative + content generation.

```env
LLM_PROVIDER=anthropic          # or "openai"
ANTHROPIC_API_KEY=              # required only for LLM features
ANTHROPIC_MODEL=claude-opus-4-8
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o
FRONTEND_ORIGIN=http://localhost:3000
PRODUCT_CACHE_TTL_SECONDS=600
SESSION_TTL_SECONDS=3600
REQUEST_TIMEOUT_SECONDS=20
HTTP_USER_AGENT=HealfProductIntelligenceMVP/1.0
```

**Frontend (`frontend/.env.local`):**

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## 8. Run locally

```bash
# Terminal 1 — backend
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open **http://localhost:3000**, paste `https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack`
and ask a question.

## 9. Run with Docker

```bash
cp backend/.env.example backend/.env    # add a key for LLM features (optional)
docker compose up --build
# frontend http://localhost:3000 · backend http://localhost:8000
```

## 10. API examples

```bash
# Health
curl http://localhost:8000/health
# {"status":"ok","llm_configured":false}

# Fetch a product (debug/tests)
curl -X POST http://localhost:8000/api/products/fetch \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack"}'

# Chat (non-streaming)
curl -X POST http://localhost:8000/api/chat -H 'Content-Type: application/json' \
  -d '{"message":"https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack\nDoes it contain Vitamin D?"}'

# Chat (SSE stream): events status → product → token → complete
curl -N -X POST http://localhost:8000/api/chat/stream -H 'Content-Type: application/json' \
  -d '{"session_id":"<from previous>","message":"What can I improve on this page?"}'
```

## 11. Supported question types

`review_lookup` · `ingredient_lookup` (alias-aware) · `price_lookup` · `subscription_lookup` ·
`availability_lookup` · `image_evaluation` · `page_evaluation` · `seo_evaluation` ·
`content_rewrite` · `faq_generation` · `product_summary` · `general_product_question`.

## 12. Example outputs

Real, unedited responses captured from the live backend:
[`examples/example_outputs.md`](examples/example_outputs.md). Highlights (LMNT Recharge):

- **Reviews:** "Yes — 516 reviews, 4.9/5" (aggregate only; individual text not ingested).
- **Vitamin D:** *"Vitamin D is **not listed** in the ingredients available on the live page"* —
  never "does not contain".
- **Magnesium:** "**Yes — magnesium is listed**" (matched `magnesium malate`).
- **Evaluation:** 89/100 heuristic; weakest = Image coverage (46, 0% alt text) → prioritized fix.

## 13. Data extraction strategy

Layered, most-reliable first, merged by precedence (see `docs/architecture.md`):

1. **Shopify probe** `/products/{h}.js|.json` (locale-first) — graceful 404 on Healf.
2. **Embedded flight JSON** — variants, price range, compare-at, selling plans (subscription %),
   images (`src`/`altText`), SEO, availability. *(Primary source on Healf.)*
3. **JSON-LD `Product`** — reviews (`aggregateRating` → count + rating), offers, brand.
4. **HTML accordions** — description, "Why … is Healf", ingredients (split into flavour groups),
   suggested use, warnings; plus `<meta>` for SEO/canonical.
5. **Image / review fallbacks** from rendered HTML when structured sources are thin.

Images are **unioned** across sources and deduped by canonical URL. Every field keeps evidence
(source type, URL, excerpt, selector, confidence); conflicts add a warning and lower confidence.

## 14. LLM usage

The LLM (Anthropic or OpenAI, selectable via `LLM_PROVIDER`) is used **only** for open-ended work:
evaluation narrative + prioritized recommendations, product summary, general questions, and content
generation (rewrite / FAQ / SEO). It receives a **compact fact payload — never raw HTML** — and must
return JSON matching the requested schema. Prompts live in `backend/app/prompts/`.

## 15. Grounding & hallucination controls

- Factual questions are answered **deterministically** from `ProductData` — the LLM is not in the loop.
- Ingredient lookups use three states — **present / not_listed / unknown** — and never claim absence
  from mere non-listing.
- The LLM is instructed not to invent ingredients, quantities, prices, ratings, certifications, or
  medical claims; content generation returns *claims preserved* and *claims not introduced*.
- Missing vs. unretrievable information is distinguished throughout; evaluation is labelled **heuristic**.
- Rendered markdown is sanitized; product HTML is never rendered raw; external links use `rel="noopener noreferrer"`.

## 16. Known limitations

- **No vision** — image *content* isn't inspected; nutrient *quantities* aren't OCR'd (only the ingredient list).
- **Reviews are aggregate only** (count + rating); individual review text isn't ingested.
- **Ephemeral state** — sessions/cache are in-memory; restarting clears them. Recent chats in the
  sidebar are localStorage metadata; selecting one re-establishes context on the next message.
- **Extraction is markup-dependent** — Healf's headless flight format can change; a regression suite
  is the first production task.
- **Site benchmark is optional/sampled** — if `backend/data/benchmark.json` is absent, evaluation stays
  product-specific and says so (it does not claim comparison with the whole catalogue).

## 17. Testing

```bash
# Backend — unit + integration (mocked HTTP via respx, mocked LLM; not live-only)
cd backend && pytest -q            # 68 tests

# Frontend — component tests
cd frontend && npm run test        # vitest
npm run typecheck && npm run build # type + build gates
```

Parser tests run against a **sanitized live fixture** (`backend/tests/fixtures/lmnt_recharge.html`).
A live smoke test: `python scripts/probe_fixture.py` (offline) or hit the running API (§10).

## 18. Production changes

Replace in-memory sessions/cache with Postgres/Redis; add auth, rate limiting, audit logs, model
fallback, prompt/schema versioning, OpenTelemetry, content moderation, snapshot storage, and an
extraction regression suite. Full list in [`docs/roadmap.md`](docs/roadmap.md).

## 19. Three-month roadmap

Month 1 reliability & scale → Month 2 multimodal (vision, OCR, alt-text gen, review sentiment) →
Month 3 operational integration (Shopify Admin writes, approval workflow, scheduled audits). See
[`docs/roadmap.md`](docs/roadmap.md).

## 20. Repository structure

```
├── README.md
├── docker-compose.yml
├── docs/                       # architecture.md · roadmap.md
├── examples/                   # example_outputs.md (live) · screenshots/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI: /health /api/products/fetch /api/chat /api/chat/stream
│   │   ├── chat_service.py     # shared pipeline (session + ingest + compose)
│   │   ├── config.py
│   │   ├── models/             # product · evaluation · api (Pydantic v2)
│   │   ├── navigation/         # url_parser · validator (SSRF) · healf_client
│   │   ├── ingestion/          # embedded_json · jsonld · html · images · reviews · shopify · merger · ingest
│   │   ├── intelligence/       # intent_router · factual_answerer · evaluation_rules · evaluator · content_generator · response_composer · llm_client
│   │   ├── context/            # session_store · benchmark_store
│   │   ├── prompts/            # evaluator · writer
│   │   └── utilities/          # text · currency · logging
│   ├── scripts/                # build_benchmark.py · capture_examples.py · probe_fixture.py
│   └── tests/                  # url · validator · parsers · merger · factual · evaluation · api · healf_client
└── frontend/
    ├── app/                    # layout · page · globals.css · api/health
    ├── components/             # chat/ · product/ · intelligence/ · ui/
    ├── lib/                    # api (SSE) · types · utils · local-history
    └── test/                   # vitest component tests
```

---

_Built as a scoped MVP: strong grounding, useful conversation, and a clear path to production._
