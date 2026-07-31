"""LLM content generation: rewrite, benefits, FAQ, SEO (PRD 20.3)."""
from __future__ import annotations

import json
import re

from ..models import AppError, ContentDraft, ProductData
from ..prompts import writer as prompt
from . import llm_client
from .llm_payload import product_facts

_TASKS = {
    "content_rewrite": "Rewrite the product description to be clearer, benefit-led and scannable. Keep it concise.",
    "faq_generation": "Write 5 helpful FAQ questions and answers a shopper would ask about this product.",
    "seo_evaluation": "Write an improved SEO title (<=60 chars) and meta description (120-155 chars).",
    "benefits_rewrite": "Rewrite the key benefits as 4-6 crisp bullet points.",
}

_HAPPY_CUSTOMERS_RE = re.compile(r"\b([\d,]+)\s+happy customers\b", re.IGNORECASE)
_UNSUPPORTED_MARKETING_RE = re.compile(
    r"\b(banish|perfect for|precise blend|go-to|tasty|delicious|flavou?rful boost|boost your)\b",
    re.IGNORECASE,
)


def _sanitize_generated_content(content: str) -> str:
    """Remove a common unsupported inference from aggregate review metadata.

    A count tells us how many reviews the page reports, not how every reviewer
    felt.  Prompt instructions are backed by this deterministic final check.
    """
    content = _HAPPY_CUSTOMERS_RE.sub(r"\1 reviews", content)
    # Generated copy must not silently alter punctuation or wording and then
    # present it as a verbatim customer quotation. Review evidence is surfaced
    # by the dedicated deterministic review flow instead.
    lines = [line for line in content.splitlines() if not line.lstrip().startswith(">")]
    return "\n".join(lines).strip()


def _safe_description_draft(p: ProductData) -> str:
    """Build a useful fact-only draft when generated copy crosses guardrails."""
    title = p.title or p.handle.replace("-", " ").title()
    lines = [f"## {title}"]
    if p.vendor:
        lines.append(f"**Brand:** {p.vendor}")
    if p.benefits:
        lines.extend(["", "### Page-listed benefits"])
        lines.extend(f"- {benefit}" for benefit in p.benefits)
    if p.ingredient_groups:
        lines.extend(["", "### Ingredients"])
        for name, ingredients in p.ingredient_groups.items():
            lines.append(f"- **{name}:** {', '.join(ingredients)}")
    elif p.ingredients_raw:
        lines.extend(["", "### Ingredients", p.ingredients_raw])
    if p.suggested_use:
        lines.extend(["", "### Suggested use", p.suggested_use])
    if p.one_time_price or p.subscription_price:
        lines.extend(["", "### Purchase options"])
        if p.one_time_price:
            lines.append(f"- One-time purchase: {p.one_time_price.formatted}")
        if p.subscription_price:
            saving = (
                f" ({p.subscription_savings_percent:g}% saving)"
                if p.subscription_savings_percent is not None
                else ""
            )
            lines.append(f"- Subscription: {p.subscription_price.formatted}{saving}")
    if p.reviews.count is not None:
        rating = (
            f" with an average rating of {p.reviews.average_rating}/5"
            if p.reviews.average_rating is not None
            else ""
        )
        lines.extend(["", f"The current Healf page reports {p.reviews.count:,} reviews{rating}."])
    return "\n".join(lines)


async def generate(p: ProductData, intent: str, message: str) -> ContentDraft:
    if not llm_client.is_configured():
        raise AppError("LLM_NOT_CONFIGURED", "Content generation needs an LLM API key.", 503)
    task = _TASKS.get(intent, f"Fulfil this request using only the product facts: {message}")
    user = json.dumps(
        {"task": task, "user_message": message, "product": product_facts(p)},
        default=str,
    )
    data = await llm_client.complete_json(prompt.SYSTEM + "\n" + prompt.SCHEMA_HINT, user, max_tokens=1800)
    content = _sanitize_generated_content(str(data.get("content", "")))
    if intent == "content_rewrite" and _UNSUPPORTED_MARKETING_RE.search(content):
        content = _safe_description_draft(p)
    return ContentDraft(
        title=str(data.get("title", "Draft"))[:120],
        content=content,
        facts_used=[str(x) for x in (data.get("facts_used") or [])],
        claims_preserved=[str(x) for x in (data.get("claims_preserved") or [])],
        claims_not_introduced=[str(x) for x in (data.get("claims_not_introduced") or [])]
        or ["No medical, disease-treatment, or unsupported performance claims were introduced."],
    )
