"""Route intent -> answer/evaluation/content and assemble the response (PRD 8, 21)."""
from __future__ import annotations

import json

from ..models import (
    ChatAnswer,
    ContentDraft,
    ProductData,
    ProductEvaluation,
    SourceEvidence,
)
from . import content_generator, evaluator, factual_answerer as fa, llm_client
from .intent_router import IntentResult, classify
from .llm_payload import product_facts
from ..prompts import evaluator as eval_prompt

def suggest_follow_ups(
    product: ProductData, current_intent: str, asked_intents: frozenset[str] = frozenset()
) -> list[str]:
    """Build follow-up prompts from what THIS product actually has, skipping any
    action already asked earlier in the conversation. Deterministic, no LLM call."""
    done = set(asked_intents) | {current_intent}
    # (prompt, the intent it maps to, is-it-relevant-for-this-product)
    candidates: list[tuple[str, str, bool]] = [
        ("What can I improve on this page?", "page_evaluation", True),
        ("Check the ingredients", "ingredient_lookup", bool(product.ingredients_raw or product.ingredient_groups)),
        ("Compare one-time vs subscription pricing", "subscription_lookup", bool(product.subscription_price)),
        ("What is the rating?", "review_lookup", bool(product.reviews.present)),
        ("Does it have reviews?", "review_lookup", product.reviews.present is None),
        ("Rewrite the description", "content_rewrite", bool(product.description_text)),
        ("Create a better FAQ", "faq_generation", True),
        ("Are the images good enough?", "image_evaluation", bool(product.images)),
        ("Improve the SEO title and meta description", "seo_evaluation", True),
        ("Is it in stock?", "availability_lookup", product.available is not None),
        ("Summarize the product", "product_summary", True),
    ]
    out: list[str] = []
    for prompt, ikey, relevant in candidates:
        if relevant and ikey not in done:
            out.append(prompt)
            done.add(ikey)  # don't offer two prompts for the same intent
        if len(out) == 3:
            break
    return out


class Composed:
    def __init__(self):
        self.answer: ChatAnswer | None = None
        self.evaluation: ProductEvaluation | None = None
        self.content_draft: ContentDraft | None = None
        self.evidence: list[SourceEvidence] = []
        self.suggested_actions: list[str] = []


def _evidence_for(product: ProductData, fields: list[str]) -> list[SourceEvidence]:
    if not fields:
        return product.evidence
    return [e for e in product.evidence if e.field in fields] or product.evidence


async def compose(product: ProductData, message: str, prior_user_messages: list[str] | None = None) -> Composed:
    intent = classify(message)
    out = Composed()
    asked = frozenset(classify(m).intent for m in (prior_user_messages or []))
    out.suggested_actions = suggest_follow_ups(product, intent.intent, asked)

    i = intent.intent
    if i == "ingredient_lookup":
        out.answer = fa.answer_ingredient(product, intent.target_entity)
        out.evidence = _evidence_for(product, ["ingredients_raw", "ingredient_groups"])
    elif i == "review_lookup":
        out.answer = fa.answer_reviews(product)
        out.evidence = _evidence_for(product, ["reviews"])
    elif i == "price_lookup":
        out.answer = fa.answer_price(product)
        out.evidence = _evidence_for(product, ["one_time_price", "compare_at_price", "subscription_price"])
    elif i == "subscription_lookup":
        out.answer = fa.answer_subscription(product)
        out.evidence = _evidence_for(product, ["subscription_price", "selling_plans", "one_time_price"])
    elif i == "availability_lookup":
        out.answer = fa.answer_availability(product)
        out.evidence = _evidence_for(product, ["available"])
    elif i in ("page_evaluation", "seo_evaluation", "image_evaluation"):
        await _handle_evaluation(product, message, i, out)
    elif i in ("content_rewrite", "faq_generation"):
        await _handle_content(product, message, i, out)
    elif i == "product_summary":
        await _handle_summary(product, message, out)
    else:  # general_product_question
        await _handle_general(product, message, out)

    return out


async def _handle_evaluation(product, message, intent, out: Composed) -> None:
    out.evaluation = await evaluator.evaluate(product, message)
    ev = out.evaluation
    cats = sorted(ev.categories, key=lambda c: c.score)
    lines = [ev.summary, "", f"**Overall score: {ev.overall_score}/100** (a heuristic, not an exact grade)."]
    if cats:
        strongest, weakest = cats[-1], cats[0]
        lines.append(
            f"Strongest area: **{strongest.label}** ({strongest.score}/100). "
            f"Weakest: **{weakest.label}** ({weakest.score}/100)."
        )
    if ev.recommendations:
        lines.append(f"\nThe {min(len(ev.recommendations), 3)} highest-impact fixes are in the card below.")
    conf = "medium" if ev.provisional else "high"
    out.answer = ChatAnswer(text="\n".join(lines), intent=intent, confidence=conf, limitations=ev.limitations)
    out.evidence = product.evidence


async def _handle_content(product, message, intent, out: Composed) -> None:
    if not llm_client.is_configured():
        out.answer = ChatAnswer(
            text="I can answer factual questions, but content generation is unavailable because no LLM is configured.",
            intent=intent,
            confidence="low",
            limitations=["Set an ANTHROPIC_API_KEY or OPENAI_API_KEY to enable content generation."],
        )
        return
    draft = await content_generator.generate(product, intent, message)
    out.content_draft = draft
    out.answer = ChatAnswer(
        text=f"Here is a draft: **{draft.title}**. See the draft card below - it lists which facts were used and which claims were deliberately not introduced.",
        intent=intent,
        confidence="medium",
        limitations=["Generated from extracted facts only; review before publishing."],
    )
    out.evidence = product.evidence


async def _handle_summary(product, message, out: Composed) -> None:
    if not llm_client.is_configured():
        out.answer = _rule_summary(product)
        return
    try:
        user = json.dumps({"task": "Summarize this product in 3-4 sentences for a shopper.", "product": product_facts(product)}, default=str)
        data = await llm_client.complete_json(
            eval_prompt.SYSTEM + '\nReturn ONLY JSON: {"summary": "..."}', user, max_tokens=500
        )
        out.answer = ChatAnswer(text=str(data.get("summary", "")) or _rule_summary(product).text, intent="product_summary", confidence="medium")
    except Exception:  # noqa: BLE001
        out.answer = _rule_summary(product)
    out.evidence = product.evidence


_GENERAL_SYSTEM = """You are a helpful assistant for a health and wellness marketplace,
answering questions about a specific product page.

You are given the user's question and structured facts extracted from the live product page.

Rules:
1. For facts about THIS product (its price, ingredients, reviews, availability, benefits,
   certifications), use only the supplied facts. If they don't contain it, say the page doesn't show it.
2. For general-knowledge questions (e.g. "what is tartaric acid?", "what is magnesium used for?"),
   you may use your own general knowledge to give a brief, helpful explanation. Make clear it is
   general information, not a claim about this specific product.
3. Never invent product-specific facts, prices, or certifications.
4. Do not give medical advice or make disease-treatment claims.
5. Be concise and friendly.

Return ONLY JSON: {"answer": "..."}"""


async def _handle_general(product, message, out: Composed) -> None:
    if not llm_client.is_configured():
        out.answer = ChatAnswer(
            text="I can answer factual questions about price, ingredients, reviews, availability and images. For open-ended questions, configure an LLM key. " + _rule_summary(product).text,
            intent="general_product_question",
            confidence="low",
        )
        return
    try:
        user = json.dumps(
            {
                "user_question": message,
                "product_facts": product_facts(product),
            },
            default=str,
        )
        data = await llm_client.complete_json(_GENERAL_SYSTEM, user, max_tokens=700)
        out.answer = ChatAnswer(
            text=str(data.get("answer", "")) or "I could not answer that.",
            intent="general_product_question",
            confidence="medium",
        )
    except Exception:  # noqa: BLE001
        out.answer = _rule_summary(product)
    out.evidence = product.evidence


def _rule_summary(product: ProductData) -> ChatAnswer:
    parts = []
    if product.title:
        parts.append(f"**{product.title}**" + (f" by {product.vendor}" if product.vendor else ""))
    if product.one_time_price:
        parts.append(f"priced at {product.one_time_price.formatted}")
    if product.reviews.count:
        parts.append(f"with {product.reviews.count:,} reviews ({product.reviews.average_rating}/5)")
    if product.benefits:
        parts.append("Key benefits: " + "; ".join(product.benefits[:3]))
    text = ". ".join(parts) + "." if parts else "I have the product loaded but limited details to summarize."
    return ChatAnswer(text=text, intent="product_summary", confidence="medium")
