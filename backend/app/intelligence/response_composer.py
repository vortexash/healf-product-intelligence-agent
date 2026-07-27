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

SUGGESTED = {
    "ingredient_lookup": ["Show all ingredients", "Check another nutrient", "Evaluate this page"],
    "review_lookup": ["What is the rating?", "Summarize the product", "What can I improve?"],
    "price_lookup": ["Compare one-time vs subscription", "Is it in stock?", "Rewrite the description"],
    "subscription_lookup": ["What is the one-time price?", "Evaluate this page", "Summarize the product"],
    "availability_lookup": ["What is the price?", "Show reviews", "Summarize the product"],
    "image_evaluation": ["What can I improve?", "Are alt texts good?", "Evaluate this page"],
    "page_evaluation": ["Rewrite the description", "Create a better FAQ", "Improve the SEO"],
    "seo_evaluation": ["Rewrite the description", "What else can I improve?", "Create an FAQ"],
    "content_rewrite": ["Create a FAQ", "Improve the SEO title", "Evaluate this page"],
    "faq_generation": ["Rewrite the description", "Improve the SEO", "What can I improve?"],
    "product_summary": ["Does it have reviews?", "Check the ingredients", "What can I improve?"],
    "general_product_question": ["Summarize the product", "Check the ingredients", "What can I improve?"],
}

_DEFAULT_SUGGESTED = ["Summarize the product", "Check the ingredients", "What can I improve?"]


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
    out.suggested_actions = SUGGESTED.get(intent.intent, _DEFAULT_SUGGESTED)

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
            lines.append(f"{r.priority}. **{r.title}** — {r.suggested_action}")
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
        text=f"Here is a draft: **{draft.title}**. See the draft card below — it lists which facts were used and which claims were deliberately not introduced.",
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
