# Diagrams

These are [Mermaid](https://mermaid.js.org/) diagrams; they render on GitHub, in VS Code with the
Markdown Preview Mermaid extension, and in most Markdown viewers.

1. [System / container overview](#1-system--container-overview)
2. [User flow](#2-user-flow)
3. [Request sequence (streaming, end-to-end)](#3-request-sequence-end-to-end)
4. [Backend module architecture](#4-backend-module-architecture)
5. [Ingestion data flow](#5-ingestion-data-flow)
6. [Frontend component tree](#6-frontend-component-tree)
7. [Data model](#7-data-model)

---

## 1. System / container overview

The big picture: a browser talking to a FastAPI backend, which talks to two external systems
(the live Healf site and an LLM provider). No database — state is in memory.

```mermaid
flowchart LR
    subgraph Client["Browser"]
        UI["Next.js Chat UI<br/>(TypeScript · Tailwind)"]
        LS["localStorage<br/>recent chats"]
        UI <--> LS
    end

    subgraph Server["Backend - FastAPI (Python)"]
        API["HTTP API<br/>/health · /api/products/fetch<br/>/api/chat · /api/chat/stream"]
        CAP1["Navigate"]
        CAP2["Ingest"]
        CAP3["Evaluate"]
        CAP4["Act"]
        MEM["In-memory<br/>Session store + Product cache"]
        API --> CAP1 --> CAP2 --> CAP3 --> CAP4
        API <--> MEM
    end

    subgraph External["External"]
        HEALF["healf.com<br/>(live product pages)"]
        LLM["LLM Provider<br/>(Anthropic / OpenAI)"]
    end

    UI -- "POST message (SSE)" --> API
    API -- "status·product·token·complete" --> UI
    CAP1 -- "HTTPS GET (SSRF-safe)" --> HEALF
    CAP3 -- "facts only, never raw HTML" --> LLM
    CAP4 -- "facts only" --> LLM
```

---

## 2. User flow

What a user actually does, and how the agent responds. Note the follow-up loop needs **no URL**.

```mermaid
flowchart TD
    A([User opens chat]) --> B["Paste Healf URL + question<br/>e.g. 'Does it contain Vitamin D?'"]
    B --> C{Valid Healf<br/>product URL?}
    C -- No --> C1["Friendly error<br/>(INVALID_URL / UNSUPPORTED_HOST)"] --> B
    C -- Yes --> D["Agent fetches + ingests the live page<br/>(progress shown live)"]
    D --> E["Product card appears"]
    E --> F{Question type?}
    F -- "Factual<br/>(reviews / ingredient / price)" --> G["Deterministic answer + Sources"]
    F -- "Evaluation<br/>('what can I improve?')" --> H["Scorecard + LLM recommendations"]
    F -- "Content<br/>('rewrite the description')" --> I["Draft + claims preserved/not-introduced"]
    G --> J["Follow-up question<br/>(no URL needed)"]
    H --> J
    I --> J
    J -- "reuses active product from session" --> F
    J --> K([Open Evidence drawer<br/>to see provenance])
```

---

## 3. Request sequence (end-to-end)

The full lifecycle of one streamed message, across every layer. This is the diagram to show when
asked *"what happens when I hit send?"*

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant FE as Frontend (chat-shell + lib/api)
    participant API as FastAPI (main.py)
    participant CS as chat_service.pipeline
    participant NAV as navigation<br/>(url_parser, validator, healf_client)
    participant HF as healf.com
    participant ING as ingestion (6 parsers + merger)
    participant INT as intelligence (router → composer)
    participant LLM as LLM provider

    U->>FE: type URL + question, press Enter
    FE->>API: POST /api/chat/stream (SSE)
    API->>CS: pipeline(session, message)

    CS->>NAV: extract + validate URL
    NAV-->>CS: normalized handle/locale/variant
    API-->>FE: event: status "Validating Healf URL"

    alt product not cached
        CS->>NAV: fetch(url)
        NAV->>NAV: SSRF host check (+ each redirect)
        NAV->>HF: HTTPS GET
        HF-->>NAV: HTML (Next.js flight + JSON-LD)
        API-->>FE: event: status "Opening product page"
        CS->>ING: run parsers → merge
        ING-->>CS: ProductData + evidence
        API-->>FE: event: status "Extracting…"
    else cached (≤10 min)
        CS-->>CS: return cached ProductData
    end

    API-->>FE: event: product { rich card }
    CS->>INT: compose(product, message)
    INT->>INT: classify intent
    alt factual (deterministic)
        INT-->>CS: answer (no LLM)
    else evaluation / content
        INT->>LLM: facts + signals (never raw HTML)
        LLM-->>INT: JSON (narrative / draft)
        INT-->>CS: answer + evaluation/draft
    end
    API-->>FE: event: token … (streamed text)
    API-->>FE: event: complete { full response + evidence }
    FE-->>U: render answer, sources, cards
```

---

## 4. Backend module architecture

The four capabilities as isolated layers (this is the "distinct capabilities / easy to extend"
answer). Each box is a real folder/file.

```mermaid
flowchart TD
    MAIN["main.py<br/>FastAPI endpoints + SSE"] --> SVC["chat_service.py<br/>pipeline + session"]

    subgraph NAV["navigation/ (Navigate)"]
        UP["url_parser.py<br/>validate + normalize"]
        VAL["validator.py<br/>SSRF guard"]
        HC["healf_client.py<br/>live fetch + retries"]
    end

    subgraph ING["ingestion/ (Ingest)"]
        EJ["embedded_json_parser.py<br/>(RSC flight JSON)"]
        JL["jsonld_parser.py<br/>(reviews/offers)"]
        HP["html_parser.py<br/>(accordions)"]
        SP["shopify_parser.py"]
        RP["reviews_parser.py"]
        IP["images_parser.py"]
        MG["merger.py<br/>precedence + evidence"]
        EJ & JL & HP & SP & RP & IP --> MG
    end

    subgraph INT["intelligence/ (Evaluate + Act)"]
        IR["intent_router.py"]
        FA["factual_answerer.py<br/>(deterministic)"]
        ER["evaluation_rules.py<br/>(scorecard)"]
        EV["evaluator.py<br/>(+ LLM)"]
        CG["content_generator.py<br/>(+ LLM)"]
        RC["response_composer.py"]
        LC["llm_client.py"]
        IR --> RC
        RC --> FA & EV & CG
        ER --> EV
        EV & CG --> LC
    end

    subgraph CTX["context/"]
        SS["session_store.py<br/>sessions + cache"]
        BS["benchmark_store.py"]
    end

    SVC --> UP --> VAL --> HC --> MG
    SVC --> IR
    SVC <--> SS
    EV --> BS
    MG --> PD["ProductData<br/>(normalized + evidence)"]
    PD --> RC
```

---

## 5. Ingestion data flow

How raw HTML becomes one normalized product. The **merger** is the key: many sources in, one
authoritative value per field out, with evidence and conflict tracking.

```mermaid
flowchart LR
    HTML["Live page HTML<br/>(Next.js flight + JSON-LD + accordions)"]

    HTML --> P1["embedded_json<br/>variants, price, subs, images, SEO"]
    HTML --> P2["json_ld<br/>reviews, brand, offers"]
    HTML --> P3["html<br/>description, ingredients, suggested use"]
    HTML --> P4["images / reviews<br/>fallbacks"]

    P1 --> M{{"merger.py<br/>precedence · overrides ·<br/>image union · conflicts"}}
    P2 --> M
    P3 --> M
    P4 --> M

    M --> PD["ProductData"]
    PD --> F1["fields: title, price,<br/>ingredients, reviews, images…"]
    PD --> F2["evidence[]: each field's<br/>source + excerpt + confidence"]
    PD --> F3["extraction_warnings[]:<br/>conflicts / missing sections"]

    note["Precedence:<br/>embedded_json &gt; json_ld &gt; html &gt; review_widget &gt; derived<br/>(SEO prefers HTML meta · reviews prefer JSON-LD)"]
    M -.-> note
```

---

## 6. Frontend component tree

```mermaid
flowchart TD
    PAGE["app/page.tsx"] --> SHELL["ChatShell<br/>(state: session, messages,<br/>active product, streaming)"]

    SHELL --> SB["ChatSidebar<br/>(new chat + recent)"]
    SHELL --> MAIN2["Message thread"]
    SHELL --> COMP["ChatComposer<br/>(input + product chip)"]
    SHELL --> DRAWER["EvidenceDrawer"]

    MAIN2 --> MSG["Message (per turn)"]
    MSG --> PROG["AgentProgress<br/>(live status steps)"]
    MSG --> PC["ProductCard"]
    MSG --> ANS["Answer (markdown)<br/>+ Citations (Sources row)"]
    MSG --> ICARD["IngredientCard"]
    MSG --> RCARD["ReviewSummaryCard"]
    MSG --> SCORE["Scorecard + Recommendations"]
    MSG --> DRAFT["ContentDraftCard"]
    MSG --> CHIPS["PromptChips (follow-ups)"]

    LIBAPI["lib/api.ts<br/>streamChat() — parses SSE"]
    SHELL <--> LIBAPI
    LIBAPI <-->|"/api/chat/stream"| BE(["FastAPI backend"])
```

---

## 7. Data model

The core `ProductData` and the evidence that grounds every field.

```mermaid
classDiagram
    class ProductData {
        +str source_url
        +str handle
        +datetime retrieved_at
        +str title
        +str vendor
        +str description_text
        +str[] benefits
        +str ingredients_raw
        +dict ingredient_groups
        +bool available
        +SourceEvidence[] evidence
        +str[] extraction_warnings
    }
    class Money { +float amount; +str currency; +str formatted }
    class ProductImage { +str url; +str alt_text; +bool is_primary }
    class ProductVariant { +str id; +str title; +bool available }
    class SellingPlan { +str name; +float discount_percent }
    class ReviewSummary { +bool present; +int count; +float average_rating; +bool full_review_text_ingested }
    class SeoData { +str title; +str description; +str canonical_url }
    class SourceEvidence { +str field; +str source_type; +str source_url; +str excerpt; +float confidence }

    ProductData "1" --> "1" Money : one_time_price / subscription_price
    ProductData "1" --> "*" ProductImage : images
    ProductData "1" --> "*" ProductVariant : variants
    ProductData "1" --> "*" SellingPlan : selling_plans
    ProductData "1" --> "1" ReviewSummary : reviews
    ProductData "1" --> "1" SeoData : seo
    ProductData "1" --> "*" SourceEvidence : evidence

    class ProductEvaluation {
        +int overall_score
        +str summary
        +EvaluationCategory[] categories
        +Recommendation[] recommendations
    }
    ProductEvaluation ..> ProductData : evaluates
```
