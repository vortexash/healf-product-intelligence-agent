"""Deterministic evaluation signals + heuristic scorecard (PRD 18).

Produces per-category signals and a weighted overall score. This is a heuristic,
not exact science — it is labelled as such. The LLM stage consumes these signals.
"""
from __future__ import annotations

from ..models import EvaluationCategory, ProductData
from ..utilities import word_count

WEIGHTS = {
    "description": 0.20,
    "completeness": 0.20,
    "ingredients": 0.15,
    "images": 0.15,
    "reviews": 0.10,
    "pricing": 0.10,
    "seo": 0.10,
}

LABELS = {
    "description": "Description quality",
    "completeness": "Information completeness",
    "ingredients": "Ingredient transparency",
    "images": "Image coverage",
    "reviews": "Review evidence",
    "pricing": "Pricing clarity",
    "seo": "SEO basics",
}


def compute_signals(p: ProductData) -> dict:
    """Raw structured signals — also passed to the LLM evaluator."""
    desc_words = word_count(p.description_text)
    alt = sum(1 for i in p.images if i.alt_text)
    dup_ratio = 0.0
    if p.images:
        dup_ratio = 1 - (len({i.url for i in p.images}) / len(p.images))
    return {
        "description": {
            "exists": bool(p.description_text),
            "word_count": desc_words,
            "paragraph_count": (p.description_text or "").count("\n\n") + 1 if p.description_text else 0,
            "has_benefits": bool(p.benefits),
            "has_suggested_use": bool(p.suggested_use),
            "has_warnings": bool(p.warnings),
            "too_short": 0 < desc_words < 60,
        },
        "ingredients": {
            "section_exists": bool(p.ingredients_raw),
            "non_empty": bool(p.ingredients_raw and len(p.ingredients_raw) > 10),
            "groups_separated": len(p.ingredient_groups) > 1,
            "group_count": len(p.ingredient_groups),
            "has_warnings": bool(p.warnings),
        },
        "reviews": {
            "present": bool(p.reviews.present),
            "count": p.reviews.count,
            "rating": p.reviews.average_rating,
            "full_text": p.reviews.full_review_text_ingested,
        },
        "images": {
            "count": len(p.images),
            "alt_coverage": round(alt / len(p.images), 2) if p.images else 0.0,
            "has_primary": any(i.is_primary for i in p.images),
            "duplicate_ratio": round(dup_ratio, 2),
        },
        "pricing": {
            "one_time": bool(p.one_time_price),
            "subscription": bool(p.subscription_price),
            "savings_clear": p.subscription_savings_percent is not None,
            "variants": len(p.variants),
            "availability_known": p.available is not None,
        },
        "seo": {
            "title": bool(p.seo.title),
            "description": bool(p.seo.description),
            "canonical": bool(p.seo.canonical_url or p.canonical_url),
            "title_len": len(p.seo.title or ""),
            "desc_len": len(p.seo.description or ""),
            "brand_in_title": bool(p.vendor and p.seo.title and p.vendor.lower() in p.seo.title.lower()),
        },
    }


def _score_description(s) -> tuple[int, list[str]]:
    d = s["description"]
    f = []
    score = 0
    if d["exists"]:
        score += 35
        wc = d["word_count"]
        if wc >= 200:
            score += 25
        elif wc >= 100:
            score += 15
        else:
            f.append(f"Description is short ({wc} words).")
        if d["has_benefits"]:
            score += 20
        else:
            f.append("No key-benefit bullets found.")
        if d["paragraph_count"] > 1:
            score += 10
        if d["has_suggested_use"]:
            score += 10
    else:
        f.append("No product description found.")
    return min(score, 100), f


def _score_completeness(s) -> tuple[int, list[str]]:
    checks = [
        s["description"]["exists"],
        s["description"]["has_benefits"],
        s["ingredients"]["section_exists"],
        s["description"]["has_suggested_use"],
        s["reviews"]["present"],
        s["images"]["count"] >= 3,
        s["pricing"]["one_time"],
    ]
    score = round(100 * sum(checks) / len(checks))
    f = []
    if not s["ingredients"]["section_exists"]:
        f.append("Missing ingredients/nutrition section.")
    if not s["description"]["has_suggested_use"]:
        f.append("Missing suggested-use / directions.")
    return score, f


def _score_ingredients(s) -> tuple[int, list[str]]:
    i = s["ingredients"]
    if not i["section_exists"]:
        return 0, ["No ingredients section on the page."]
    score = 55
    f = []
    if i["groups_separated"]:
        score += 25
    if i["has_warnings"]:
        score += 20
    else:
        f.append("No allergen/warning information found.")
    return min(score, 100), f


def _score_images(s) -> tuple[int, list[str]]:
    im = s["images"]
    f = []
    if im["count"] == 0:
        return 0, ["No product images extracted."]
    score = min(im["count"], 5) * 12  # up to 60
    if im["has_primary"]:
        score += 10
    score += round(im["alt_coverage"] * 30)
    if im["alt_coverage"] < 0.5:
        f.append(f"Low alt-text coverage ({int(im['alt_coverage']*100)}%).")
    if im["count"] < 3:
        f.append(f"Only {im['count']} image(s); galleries usually have more.")
    if im["duplicate_ratio"] > 0.2:
        f.append("Duplicate images detected.")
    return min(score, 100), f


def _score_reviews(s) -> tuple[int, list[str]]:
    r = s["reviews"]
    if not r["present"]:
        return 20, ["No reviews present on the page."]
    score = 60
    f = ["Individual review text was not ingested (aggregate only)."]
    if r["count"]:
        score += min(r["count"], 100) // 5  # up to +20
    if r["rating"]:
        score += 20
    return min(score, 100), f


def _score_pricing(s) -> tuple[int, list[str]]:
    p = s["pricing"]
    f = []
    score = 0
    if p["one_time"]:
        score += 45
    else:
        f.append("No one-time price found.")
    if p["subscription"]:
        score += 25
        if p["savings_clear"]:
            score += 15
        else:
            f.append("Subscription savings % not clearly stated.")
    if p["availability_known"]:
        score += 15
    return min(score, 100), f


def _score_seo(s) -> tuple[int, list[str]]:
    seo = s["seo"]
    f = []
    score = 0
    if seo["title"]:
        score += 30
        if not (30 <= seo["title_len"] <= 65):
            f.append(f"SEO title length ({seo['title_len']}) outside 30–65 chars.")
    else:
        f.append("Missing SEO title.")
    if seo["description"]:
        score += 30
        if not (70 <= seo["desc_len"] <= 160):
            f.append(f"Meta description length ({seo['desc_len']}) outside 70–160 chars.")
    else:
        f.append("Missing meta description.")
    if seo["canonical"]:
        score += 20
    if seo["brand_in_title"]:
        score += 20
    return min(score, 100), f


_SCORERS = {
    "description": _score_description,
    "completeness": _score_completeness,
    "ingredients": _score_ingredients,
    "images": _score_images,
    "reviews": _score_reviews,
    "pricing": _score_pricing,
    "seo": _score_seo,
}

_STATUS = [(85, "strong"), (70, "good"), (50, "moderate"), (1, "weak")]


def _status(score: int) -> str:
    for threshold, label in _STATUS:
        if score >= threshold:
            return label
    return "unknown"


EVIDENCE_FIELDS = {
    "description": ["description_text", "benefits"],
    "completeness": ["description_text", "ingredients_raw", "suggested_use", "reviews", "images"],
    "ingredients": ["ingredients_raw", "ingredient_groups", "warnings"],
    "images": ["images"],
    "reviews": ["reviews"],
    "pricing": ["one_time_price", "subscription_price", "available"],
    "seo": ["seo", "canonical_url"],
}


def build_scorecard(p: ProductData) -> tuple[list[EvaluationCategory], int, dict]:
    signals = compute_signals(p)
    categories: list[EvaluationCategory] = []
    weighted = 0.0
    for key, scorer in _SCORERS.items():
        score, findings = scorer(signals)
        categories.append(
            EvaluationCategory(
                key=key,
                label=LABELS[key],
                score=score,
                status=_status(score),
                findings=findings,
                evidence_fields=EVIDENCE_FIELDS[key],
            )
        )
        weighted += score * WEIGHTS[key]
    return categories, round(weighted), signals
