"""Chat pipeline shared by /api/chat and /api/chat/stream (PRD 8.3, 22.3)."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .context import product_cache, sessions
from .context.session_store import Session
from .ingestion import ingest_product
from .intelligence import compose
from .models import AppError, ChatAnswer, ChatResponse, ProductData
from .navigation import extract_url, parse_and_validate

# Pipeline yields (kind, payload) tuples; both endpoints consume the same stream.
Event = tuple[str, object]


async def pipeline(session: Session, message: str, product_url: str | None) -> AsyncIterator[Event]:
    # 1. Resolve which product this message is about.
    raw_url = product_url or extract_url(message)
    product: ProductData | None = None

    if raw_url:
        yield ("status", {"step": "validate_url", "message": "Validating Healf URL"})
        parsed = parse_and_validate(raw_url)  # raises AppError on bad URL
        cached = product_cache.get(parsed.normalized_url)
        if cached:
            yield ("status", {"step": "cache_hit", "message": "Loading cached product"})
            product = cached
        else:
            yield ("status", {"step": "fetch_product", "message": "Opening product page"})
            yield ("status", {"step": "read_shopify", "message": "Reading Shopify product data"})
            product = await ingest_product(parsed)  # raises AppError on fetch/parse failure
            yield ("status", {"step": "extract", "message": "Extracting description, ingredients, reviews and images"})
            product_cache.set(parsed.normalized_url, product)
        session.active_product_url = parsed.normalized_url
        session.product = product
    else:
        product = session.product

    if product is None:
        raise AppError(
            "NO_ACTIVE_PRODUCT",
            "Please share a public Healf product URL (must contain /products/) so I can help.",
            400,
        )

    yield ("product", product)
    yield ("status", {"step": "answer", "message": "Preparing the answer"})

    # 2. Compose the answer.
    prior_user_messages = [m["text"] for m in session.messages if m.get("role") == "user"]
    composed = await compose(product, message, prior_user_messages)
    sessions.touch(session)
    session.messages.append({"role": "user", "text": message})
    session.messages.append({"role": "assistant", "text": composed.answer.text if composed.answer else ""})

    yield ("composed", composed)


def build_response(session: Session, product: ProductData | None, composed) -> ChatResponse:
    answer = composed.answer or ChatAnswer(text="", intent="unknown", confidence="low")
    return ChatResponse(
        session_id=session.id,
        answer=answer,
        product=product,
        evaluation=composed.evaluation,
        content_draft=composed.content_draft,
        evidence=composed.evidence,
        suggested_actions=composed.suggested_actions,
    )
