"""Hybrid question intent router (PRD 16). Deterministic keywords first."""
from __future__ import annotations

import re

from pydantic import BaseModel

from ..utilities import normalize

INTENTS = [
    "product_summary",
    "review_lookup",
    "ingredient_lookup",
    "price_lookup",
    "subscription_lookup",
    "availability_lookup",
    "image_evaluation",
    "page_evaluation",
    "seo_evaluation",
    "content_rewrite",
    "faq_generation",
    "general_product_question",
]

LLM_INTENTS = {"page_evaluation", "seo_evaluation", "content_rewrite", "faq_generation", "product_summary"}


class IntentResult(BaseModel):
    intent: str
    target_entity: str | None = None
    requires_llm: bool
    confidence: float


# Ordered rules: (intent, keyword patterns). First strong match wins.
_RULES: list[tuple[str, list[str]]] = [
    ("faq_generation", [r"\bfaq\b", r"frequently asked", r"create.*questions"]),
    ("content_rewrite", [r"\brewrite\b", r"\bre-?write\b", r"improve the (description|copy|text)", r"\brephrase\b", r"better (description|copy|version)", r"generate.*(description|copy|content)", r"draft (a|an|the)"]),
    ("seo_evaluation", [r"\bseo\b", r"meta description", r"search (engine|ranking)", r"page title"]),
    ("image_evaluation", [r"\bimages?\b", r"\bphotos?\b", r"\bpictures?\b", r"image (quality|coverage)"]),
    ("subscription_lookup", [r"\bsubscription\b", r"\bsubscribe\b", r"selling plan", r"one[- ]time vs", r"recurring"]),
    ("price_lookup", [r"\bprice\b", r"\bcost\b", r"how much", r"\bcheaper\b", r"\bexpensive\b", r"\bdiscount\b"]),
    ("availability_lookup", [r"in stock", r"\bavailable\b", r"availability", r"sold out", r"out of stock"]),
    ("review_lookup", [r"\breviews?\b", r"\bratings?\b", r"\bstars?\b", r"how many .*review"]),
    ("ingredient_lookup", [r"\bingredi", r"\bcontain", r"\binclude", r"does it have", r"\bvitamin", r"\bmagnesium\b", r"\bcaffeine\b", r"\bsugar\b", r"\ballergen", r"\bnutrition", r"is there .* in (it|this)", r"what.?s (in|inside)\b"]),
    ("page_evaluation", [r"\bimprove\b", r"what.?s (wrong|missing)", r"evaluate", r"assessment", r"how good", r"quality of (this|the) page", r"whats? missing", r"audit"]),
    ("product_summary", [r"\bsummar", r"\btell me about\b", r"what is this", r"overview", r"describe (this|the) product"]),
]


def classify(message: str) -> IntentResult:
    norm = normalize(message)
    raw = message.lower()
    for intent, patterns in _RULES:
        for pat in patterns:
            if re.search(pat, raw):
                target = _extract_target(intent, message)
                return IntentResult(
                    intent=intent,
                    target_entity=target,
                    requires_llm=intent in LLM_INTENTS,
                    confidence=0.85,
                )
    # Fallback: unclear -> general question answered with light LLM help.
    return IntentResult(
        intent="general_product_question",
        target_entity=None,
        requires_llm=True,
        confidence=0.4,
    )


def _extract_target(intent: str, message: str) -> str | None:
    if intent != "ingredient_lookup":
        return None

    # 1. Most reliable: any known ingredient (or alias) mentioned anywhere in the
    #    message, regardless of how the question is phrased.
    from .factual_answerer import INGREDIENT_ALIASES

    norm_msg = normalize(message)
    for key, aliases in INGREDIENT_ALIASES.items():
        for term in [key, *aliases]:
            if re.search(r"\b" + re.escape(term) + r"\b", norm_msg):
                return key

    # 2. "vitamin X".
    m = re.search(r"vitamin\s+[a-z0-9]+", message, re.I)
    if m:
        return m.group(0).strip()

    # 3. The word after a lookup verb, for ingredients not in the alias map.
    m = re.search(
        r"(?:contains?|have|has|includes?|with|any|is there(?:\s+any)?|got|does it have)\s+"
        r"(?:any\s+)?([a-z][a-z0-9 \-]{1,30}?)(?:\s+in\b|\s*\??$|\s*\?)",
        message,
        re.I,
    )
    if m:
        return m.group(1).strip()
    return None
