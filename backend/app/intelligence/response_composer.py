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

def suggest_follow_ups(product: ProductData, intent: str) -> list[str]:
    """Build follow-up prompts from what THIS product actually has, skipping
    whatever the user just asked. Deterministic and grounded (no LLM call)."""
    candidates: list[tuple[str, bool]] = [
        # (prompt, is-relevant-for-this-product-and-not-the-current-intent)
        ("What can I improve on this page?", intent != "page_evaluation"),
        (
            "Check the ingredients" if intent != "ingredient_lookup" else "Check another nutrient",
            bool(product.ingredients_raw or product.ingredient_groups),
        ),
        (
            "Compare one-time vs subscription pricing",
            bool(product.subscription_price) and intent not in ("subscription_lookup", "price_lookup"),
        ),
        ("What is the rating?", bool(product.reviews.present) and intent != "review_lookup"),
        ("Does it have reviews?", product.reviews.present is None and intent != "review_lookup"),
        ("Rewrite the description", bool(product.description_text) and intent != "content_rewrite"),
        ("Create a better FAQ", intent != "faq_generation"),
        ("Are the images good enough?", bool(product.images) and intent != "image_evaluation"),
        ("Improve the SEO title and meta description", intent != "seo_evaluation"),
        ("Is it in stock?", product.available is not None and intent != "availability_lookup"),
        ("Summarize the product", intent != "product_summary"),
    ]
    picks = [prompt for prompt, ok in candidates if ok]
    # De-dupe while preserving order, keep the top three.
    seen: set[str] = set()
    out: list[str] = []
    for p in picks:
        if p not in seen:
            seen.add(p)
            out.append(p)
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


async def compose(product: ProductData, message: str) -> Composed:
    intent = classify(message)
    out = Composed()
    out.suggested_actions = suggest_follow_ups(product, intent.intent)

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
    top = ev.recommendations[:3]
    lines = [ev.summary, "", f"**Overall: {ev.overall_score}/100** (heuristic)."]
    if top:
        lines.append("\n**Top recommendations:**")
        for r in top:
            lines.append(f"{r.priority}. **{r.title}** - {r.suggested_action}")
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
            {"task": "Answer the user's question using ONLY these product facts. If the facts do not contain the answer, say so.", "user_message": message, "product": product_facts(product)},
            default=str,
        )
        data = await llm_client.complete_json(
            eval_prompt.SYSTEM + '\nReturn ONLY JSON: {"answer": "..."}', user, max_tokens=700
        )
        out.answer = ChatAnswer(text=str(data.get("answer", "")) or "I could not answer that from the page.", intent="general_product_question", confidence="medium", limitations=["Answered from extracted page facts only."])
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
