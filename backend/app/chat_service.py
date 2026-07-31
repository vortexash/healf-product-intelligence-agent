"""Chat pipeline shared by /api/chat and /api/chat/stream (PRD 8.3, 22.3)."""
from __future__ import annotations

from collections.abc import AsyncIterator
import re

from .context import product_cache, sessions
from .context.session_store import Session
from .ingestion import ingest_product
from .intelligence import compose, compose_without_product
from .intelligence import product_search
from .models import AppError, ChatAnswer, ChatResponse, ConversationMessage, ProductData
from .navigation import extract_url, parse_and_validate
from .utilities import normalize

_PRODUCT_LINK_RE = re.compile(
    r"\[([^\]]{2,200})\]\((https://(?:www\.)?healf\.com/(?:[^\s)]*/)?products/[^\s)]+)\)",
    re.IGNORECASE,
)
_PRODUCT_PATH_RE = re.compile(r"/products/([^/?#]+)", re.IGNORECASE)
_ORDINALS = {
    "first": 0,
    "1st": 0,
    "one": 0,
    "second": 1,
    "2nd": 1,
    "two": 1,
    "third": 2,
    "3rd": 2,
    "three": 2,
    "fourth": 3,
    "4th": 3,
    "four": 3,
}
_REFERENCE_STOPWORDS = {
    "a", "an", "about", "can", "could", "give", "me", "please", "product",
    "tell", "the", "this", "you", "what", "is", "of", "option", "item", "one",
}
_GENERIC_NAMED_TARGETS = {
    "it", "this", "that", "this product", "that product", "the product", "product",
    "price", "reviews", "ingredients", "subscription", "images", "page", "first one",
    "second one", "third one", "fourth one",
}
_NAMED_PRODUCT_RE = re.compile(
    r"\b(tell me about|switch to|look up|open|analyse|analyze)\s+(.+?)\s*[?.!]*$",
    re.IGNORECASE,
)

# Pipeline yields (kind, payload) tuples; both endpoints consume the same stream.
Event = tuple[str, object]


async def pipeline(
    session: Session,
    message: str,
    product_url: str | None,
    client_history: list[ConversationMessage] | None = None,
    client_suggestions: list[str] | None = None,
) -> AsyncIterator[Event]:
    # Rehydrate a browser-saved conversation if the ephemeral server session
    # expired.  When the server already has turns, it remains authoritative so
    # sending history on every request cannot duplicate messages.
    if client_history and not session.messages:
        session.messages.extend(
            {"role": turn.role, "text": turn.text.strip()}
            for turn in client_history[-12:]
            if turn.text.strip()
        )

    # 1. Resolve which product this message is about.
    message_url = extract_url(message)
    # The browser sends product_url as recovery context for every turn. A
    # product explicitly selected in the new message must take precedence over
    # that older context, otherwise "tell me about X" can silently stay on Y.
    raw_url = message_url
    selected_by_reference = False
    if not raw_url:
        raw_url = _resolve_linked_product_reference(message, session.messages)
        selected_by_reference = bool(raw_url)
    if not raw_url:
        named_target = _extract_named_product_target(message)
        if named_target:
            try:
                raw_url = await product_search.find_product_url(named_target)
            except Exception as exc:  # noqa: BLE001
                raise AppError(
                    "PRODUCT_SEARCH_UNAVAILABLE",
                    "I couldn't search Healf for that product just now. Please send its Healf product URL.",
                    502,
                ) from exc
            if not raw_url:
                raise AppError(
                    "PRODUCT_REFERENCE_NOT_FOUND",
                    f"I couldn't confidently match '{named_target}' to a Healf product. Please send its product URL.",
                    404,
                )
            selected_by_reference = True
    if not raw_url:
        raw_url = product_url
    # If the backend restarted while the browser tab stayed open, the in-memory
    # session no longer knows its active product. Recover the most recent Healf
    # URL from the browser-supplied conversation so the next natural follow-up
    # works without asking the user to paste the link again.
    if not raw_url and session.product is None and client_history:
        for turn in reversed(client_history):
            if turn.role != "user":
                continue
            raw_url = extract_url(turn.text)
            if raw_url:
                break
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
        if session.active_product_url != parsed.normalized_url:
            session.suggested_actions_shown.clear()
        session.active_product_url = parsed.normalized_url
        session.product = product
    else:
        product = session.product

    if (
        client_suggestions
        and not session.suggested_actions_shown
        and not message_url
        and not selected_by_reference
    ):
        session.suggested_actions_shown.extend(dict.fromkeys(client_suggestions[-24:]))

    conversation_history = session.messages[-12:]
    if product is None:
        # A greeting or capabilities question should feel like chat, not a
        # validation error.  Stay inside the Healf-product scope and guide the
        # user to the one piece of context needed to begin grounded analysis.
        yield ("status", {"step": "answer", "message": "Preparing the answer"})
        composed = await compose_without_product(message, conversation_history)
        sessions.touch(session)
        session.messages.append({"role": "user", "text": message})
        session.messages.append({"role": "assistant", "text": composed.answer.text if composed.answer else ""})
        yield ("composed", composed)
        return

    yield ("product", product)
    yield ("status", {"step": "answer", "message": "Preparing the answer"})

    # 2. Compose the answer.
    compose_message = message
    if message_url:
        compose_message = message.replace(message_url, " ").strip() or "Tell me about this product"
    if selected_by_reference and _is_selection_summary_request(message):
        compose_message = "Tell me about this product"
    composed = await compose(
        product,
        compose_message,
        conversation_history,
        previous_suggestions=session.suggested_actions_shown,
    )
    sessions.touch(session)
    session.messages.append({"role": "user", "text": message})
    session.messages.append({"role": "assistant", "text": composed.answer.text if composed.answer else ""})
    for action in composed.suggested_actions:
        if action not in session.suggested_actions_shown:
            session.suggested_actions_shown.append(action)
    session.suggested_actions_shown = session.suggested_actions_shown[-24:]

    yield ("composed", composed)


def _resolve_linked_product_reference(message: str, history: list[dict]) -> str | None:
    """Resolve a product name or ordinal against links already shown in chat."""
    message_norm = normalize(message)
    message_tokens = set(message_norm.split()) - _REFERENCE_STOPWORDS
    ordinal = _requested_ordinal(message_norm)

    for turn in reversed(history):
        text = str(turn.get("text", ""))
        candidates = _linked_products_from_turn(turn.get("role"), text)
        if not candidates:
            continue

        for label, url in candidates:
            label_norm = normalize(label)
            if label_norm and label_norm in message_norm:
                return url
            label_tokens = set(label_norm.split()) - _REFERENCE_STOPWORDS
            overlap = len(message_tokens & label_tokens)
            if overlap >= 2 and overlap / min(len(message_tokens), len(label_tokens)) >= 0.7:
                return url

        if ordinal is not None and ordinal < len(candidates):
            return candidates[ordinal][1]
    return None


def _linked_products_from_turn(role: object, text: str) -> list[tuple[str, str]]:
    if role == "assistant":
        return [(match.group(1), match.group(2)) for match in _PRODUCT_LINK_RE.finditer(text)]
    if role == "user":
        url = extract_url(text)
        if not url:
            return []
        match = _PRODUCT_PATH_RE.search(url)
        label = match.group(1).replace("-", " ") if match else url
        return [(label, url)]
    return []


def _requested_ordinal(message_norm: str) -> int | None:
    for word, index in _ORDINALS.items():
        if re.search(rf"\b{re.escape(word)}\b", message_norm):
            return index
    number = re.search(r"\b(?:number|option|item|product)\s*([1-4])\b", message_norm)
    return int(number.group(1)) - 1 if number else None


def _extract_named_product_target(message: str) -> str | None:
    match = _NAMED_PRODUCT_RE.search(message.strip())
    if not match:
        return None
    verb = match.group(1).lower()
    target = match.group(2).strip(" \t\r\n?.!")
    target_norm = normalize(target)
    if not target_norm or target_norm in _GENERIC_NAMED_TARGETS:
        return None
    generic_tokens = {
        "the", "this", "that", "it", "its", "product", "price", "reviews",
        "rating", "ingredients", "subscription", "images", "page", "benefits",
    }
    meaningful_tokens = set(target_norm.split()) - generic_tokens
    if not meaningful_tokens:
        return None
    if len(meaningful_tokens) < 2 and verb not in {"switch to", "look up", "open"}:
        return None
    return target


def _is_selection_summary_request(message: str) -> bool:
    """True when the user is selecting a product, not asking a specific fact."""
    if not re.search(
        r"\b(?:tell me about|switch to|look up|open)\b",
        message,
        re.IGNORECASE,
    ):
        return False
    return not re.search(
        r"\b(?:price|cost|reviews?|ratings?|ingredients?|contains?|subscription|stock|"
        r"images?|seo|rewrite|compare|versus|vs\.?|available)\b",
        message,
        re.IGNORECASE,
    )


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
