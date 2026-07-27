"""LLM content generation: rewrite, benefits, FAQ, SEO (PRD 20.3)."""
from __future__ import annotations

import json

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


async def generate(p: ProductData, intent: str, message: str) -> ContentDraft:
    if not llm_client.is_configured():
        raise AppError("LLM_NOT_CONFIGURED", "Content generation needs an LLM API key.", 503)
    task = _TASKS.get(intent, f"Fulfil this request using only the product facts: {message}")
    user = json.dumps(
        {"task": task, "user_message": message, "product": product_facts(p)},
        default=str,
    )
    data = await llm_client.complete_json(prompt.SYSTEM + "\n" + prompt.SCHEMA_HINT, user, max_tokens=1800)
    return ContentDraft(
        title=str(data.get("title", "Draft"))[:120],
        content=str(data.get("content", "")),
        facts_used=[str(x) for x in (data.get("facts_used") or [])],
        claims_preserved=[str(x) for x in (data.get("claims_preserved") or [])],
        claims_not_introduced=[str(x) for x in (data.get("claims_not_introduced") or [])]
        or ["No medical, disease-treatment, or unsupported performance claims were introduced."],
    )
