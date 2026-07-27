"""LLM-backed page evaluation (PRD 18.2). Falls back to rules-only if no LLM."""
from __future__ import annotations

import json

from ..context.benchmark_store import load_benchmark
from ..models import ProductData, ProductEvaluation, Recommendation
from ..prompts import evaluator as prompt
from . import evaluation_rules, llm_client
from .llm_payload import product_facts


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
    recs.sort(key=lambda x: x.priority)
    return ProductEvaluation(
        overall_score=overall,
        summary=str(data.get("summary", ""))[:1000] or _fallback_summary(p, overall, categories),
        categories=categories,
        recommendations=recs or _fallback_recommendations(categories),
        limitations=base_limitations + [str(x) for x in (data.get("limitations") or [])],
        provisional=provisional,
    )


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
    lead = f"“{p.title}” scores {overall}/100 on a heuristic page-quality check."
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
