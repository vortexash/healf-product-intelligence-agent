"""LLM-backed page evaluation (PRD 18.2). Falls back to rules-only if no LLM."""
from __future__ import annotations

import json
import re

from ..context.benchmark_store import load_benchmark
from ..models import ProductData, ProductEvaluation, Recommendation
from ..prompts import evaluator as prompt
from . import evaluation_rules, llm_client
from .llm_payload import product_facts

_REVIEW_RE = re.compile(r"\b(review|reviews|testimonial|customer quote|social proof)\b", re.IGNORECASE)
_DIETARY_RE = re.compile(
    r"\b(allergen|allergens|dietary|certification|certified|suitability)\b",
    re.IGNORECASE,
)

# High-risk product assertions that an evaluator commonly guesses from the product
# category or ingredient list. A marker is permitted only when the same phrase is
# present in the extracted product facts/evidence.
_CLAIM_MARKERS = (
    "allergen free",
    "contains no common allergens",
    "dairy free",
    "gluten free",
    "keto friendly",
    "non gmo",
    "soy free",
    "sugar free",
    "vegan",
    "vegetarian",
    "certified",
    "supports heart",
    "heart function",
    "heart health",
    "supports muscle",
    "muscle function",
    "athletic performance",
    "high intensity workout",
    "workout essential",
)


async def evaluate(p: ProductData, question: str) -> ProductEvaluation:
    categories, overall, signals = evaluation_rules.build_scorecard(p)
    benchmark = load_benchmark()
    provisional = any(c.status == "unknown" for c in categories)

    base_limitations = [
        "This is a heuristic evaluation, not an exact score.",
        "This score judges image count and alt text, not the visual content - ask 'what do the images show?' for a visual analysis.",
    ]
    if benchmark is None:
        base_limitations.append(
            "Scored against product-specific checks only - not compared to the wider Healf catalogue."
        )

    if not llm_client.is_configured():
        # Rules-only fallback: derive recommendations from category findings.
        recs = _fallback_recommendations(categories)
        return ProductEvaluation(
            overall_score=overall,
            summary=_fallback_summary(p, overall, categories),
            categories=categories,
            recommendations=recs,
            limitations=base_limitations
            + ["Page evaluation narrative is rule-based because no LLM is configured."],
            provisional=provisional,
        )

    user = json.dumps(
        {
            "user_question": question,
            "product": product_facts(p),
            "deterministic_signals": signals,
            "category_scores": [{"key": c.key, "score": c.score, "findings": c.findings} for c in categories],
            "overall_score": overall,
            "benchmark": benchmark.model_dump() if benchmark else None,
            "benchmark_comparison": _benchmark_comparison(p, signals, benchmark),
            "evidence_fields_available": sorted({e.field for e in p.evidence}),
        },
        default=str,
    )
    try:
        data = await llm_client.complete_json(prompt.SYSTEM + "\n" + prompt.SCHEMA_HINT, user, max_tokens=2200)
    except Exception:  # noqa: BLE001 - degrade to rules-only on any LLM failure
        recs = _fallback_recommendations(categories)
        return ProductEvaluation(
            overall_score=overall,
            summary=_fallback_summary(p, overall, categories),
            categories=categories,
            recommendations=recs,
            limitations=base_limitations + ["LLM evaluation failed; showing rule-based results."],
            provisional=provisional,
        )

    recs = []
    for i, r in enumerate(data.get("recommendations", [])[:5], start=1):
        recs.append(
            Recommendation(
                priority=int(r.get("priority", i)),
                title=str(r.get("title", "Improvement"))[:120],
                rationale=str(r.get("rationale", "")),
                suggested_action=str(r.get("suggested_action", "")),
                evidence_fields=[str(x) for x in (r.get("evidence_fields") or [])],
            )
        )
    recs, guardrails_applied = _sanitize_recommendations(p, recs)
    summary = str(data.get("summary", ""))[:1000]
    if _unsupported_claim_markers(p, summary):
        summary = _fallback_summary(p, overall, categories)
        guardrails_applied = True

    limitations = base_limitations + [str(x) for x in (data.get("limitations") or [])]
    if guardrails_applied:
        limitations.append(
            "Potentially unsupported generated claims were replaced with verification-first actions."
        )

    return ProductEvaluation(
        overall_score=overall,
        summary=summary or _fallback_summary(p, overall, categories),
        categories=categories,
        recommendations=recs or _fallback_recommendations(categories),
        limitations=limitations,
        provisional=provisional,
    )


def _sanitize_recommendations(
    p: ProductData, recommendations: list[Recommendation]
) -> tuple[list[Recommendation], bool]:
    """Replace high-risk generated assertions with evidence-safe actions.

    Prompt guardrails reduce bad output, but generated merchandising copy is
    untrusted. This deterministic layer handles the failure modes with the
    highest customer and regulatory impact before recommendations reach the UI.
    """
    available_fields = {e.field for e in p.evidence}
    sanitized: list[Recommendation] = []
    seen_guardrail_topics: set[str] = set()
    changed = False

    for index, rec in enumerate(sorted(recommendations, key=lambda x: x.priority), start=1):
        rec = rec.model_copy(deep=True)
        rec.priority = index
        rec.evidence_fields = [f for f in rec.evidence_fields if f in available_fields]
        combined = " ".join((rec.title, rec.rationale, rec.suggested_action))
        review_action = " ".join((rec.title, rec.suggested_action))

        if _REVIEW_RE.search(review_action) and not p.reviews.full_review_text_ingested:
            count = f"{p.reviews.count:,}" if p.reviews.count is not None else "the available"
            rating = (
                f" at {p.reviews.average_rating}/5"
                if p.reviews.average_rating is not None
                else ""
            )
            rec.title = "Select verified review evidence"
            rec.rationale = (
                f"The page exposes aggregate data for {count} reviews{rating}, but no individual "
                "review text was ingested, so the available evidence cannot support a quotation."
            )
            rec.suggested_action = (
                "Choose a real, permissioned customer quote in the review platform, verify it "
                "against the original submission, and then add it to the page without paraphrasing."
            )
            rec.evidence_fields = _existing_fields(available_fields, "reviews")
            changed = True
        elif _unsupported_claim_markers(p, combined):
            if _contains_dietary_or_certification_marker(combined):
                rec.title = "Verify allergen and dietary information"
                rec.rationale = (
                    "The extracted page data does not verify every allergen, dietary, or "
                    "certification attribute proposed by the generated recommendation."
                )
                rec.suggested_action = (
                    "Confirm allergen, dietary, and certification status with the supplier, then "
                    "publish only the verified attributes in a dedicated section. Do not infer "
                    "suitability from the ingredient list."
                )
                rec.evidence_fields = _existing_fields(
                    available_fields, "warnings", "ingredients_raw", "description_text"
                )
            else:
                rec.title = "Substantiate product-benefit copy"
                rec.rationale = (
                    "The proposed health or performance wording is not explicitly supported by "
                    "the extracted description or benefit claims."
                )
                rec.suggested_action = (
                    "Reuse only benefit wording already approved on the product page, or ask the "
                    "brand and regulatory owners to substantiate additional claims before publishing."
                )
                rec.evidence_fields = _existing_fields(
                    available_fields, "benefits", "description_text"
                )
            changed = True

        topic = _guardrail_topic(rec)
        if topic and topic in seen_guardrail_topics:
            changed = True
            continue
        if topic:
            seen_guardrail_topics.add(topic)
        sanitized.append(rec)

    for index, rec in enumerate(sanitized, start=1):
        rec.priority = index
    return sanitized, changed


def _guardrail_topic(rec: Recommendation) -> str | None:
    title_and_action = " ".join((rec.title, rec.suggested_action))
    if _REVIEW_RE.search(title_and_action):
        return "review"
    if _DIETARY_RE.search(title_and_action):
        return "dietary"
    return None


def _existing_fields(available: set[str], *candidates: str) -> list[str]:
    return [field for field in candidates if field in available]


def _contains_dietary_or_certification_marker(text: str) -> bool:
    normalized = _normalize_claim_text(text)
    return any(
        marker in normalized
        for marker in (
            "allergen free",
            "contains no common allergens",
            "dairy free",
            "gluten free",
            "keto friendly",
            "non gmo",
            "soy free",
            "sugar free",
            "vegan",
            "vegetarian",
            "certified",
        )
    )


def _unsupported_claim_markers(p: ProductData, generated_text: str) -> list[str]:
    generated = _normalize_claim_text(generated_text)
    source = _grounding_corpus(p)
    return [marker for marker in _CLAIM_MARKERS if marker in generated and marker not in source]


def _grounding_corpus(p: ProductData) -> str:
    parts = [
        p.description_text or "",
        p.suggested_use or "",
        p.ingredients_raw or "",
        p.seo.title or "",
        p.seo.description or "",
        *p.benefits,
        *p.warnings,
        *(e.excerpt or "" for e in p.evidence),
    ]
    for name, ingredients in p.ingredient_groups.items():
        parts.append(name)
        parts.extend(ingredients)
    return _normalize_claim_text(" ".join(parts))


def _normalize_claim_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _benchmark_comparison(p: ProductData, signals: dict, benchmark) -> dict | None:
    """Ready-made 'this product vs typical Healf listing' deltas for the LLM, so it
    can cite concrete comparisons instead of guessing."""
    if not benchmark:
        return None
    desc_words = signals["description"]["word_count"]
    img_count = signals["images"]["count"]
    alt = signals["images"]["alt_coverage"]
    out: dict[str, str] = {}
    if benchmark.median_description_words:
        out["description_words"] = f"this {desc_words} vs Healf median ~{benchmark.median_description_words}"
    if benchmark.median_image_count:
        out["image_count"] = f"this {img_count} vs Healf median ~{benchmark.median_image_count}"
    if benchmark.alt_text_coverage is not None:
        out["alt_text_coverage"] = f"this {int(alt * 100)}% vs Healf average ~{int(benchmark.alt_text_coverage * 100)}%"
    if benchmark.ingredient_section_rate is not None:
        out["has_ingredients"] = (
            f"this product {'has' if signals['ingredients']['section_exists'] else 'is missing'} an "
            f"ingredients section; {int(benchmark.ingredient_section_rate * 100)}% of sampled Healf pages have one"
        )
    return out or None


def _fallback_summary(p: ProductData, overall: int, categories) -> str:
    weak = [c.label for c in categories if c.status in ("weak", "moderate")]
    lead = f'"{p.title}" scores {overall}/100 on a heuristic page-quality check.'
    if weak:
        return lead + " Weakest areas: " + ", ".join(weak[:3]) + "."
    return lead + " No major gaps detected across the checked categories."


def _fallback_recommendations(categories) -> list[Recommendation]:
    ranked = sorted(categories, key=lambda c: c.score)
    recs = []
    for i, c in enumerate(ranked[:3], start=1):
        if not c.findings:
            continue
        recs.append(
            Recommendation(
                priority=i,
                title=f"Improve {c.label.lower()}",
                rationale="; ".join(c.findings),
                suggested_action=c.findings[0],
                evidence_fields=c.evidence_fields,
            )
        )
    return recs
