"""Build a compact, fact-only product payload for the LLM (never raw HTML)."""
from __future__ import annotations

from ..models import ProductData
from ..utilities import excerpt


def product_facts(p: ProductData) -> dict:
    review_facts = {
        "present": p.reviews.present,
        "count": p.reviews.count,
        "average_rating": p.reviews.average_rating,
        "provider": p.reviews.provider,
        "full_review_text_ingested": p.reviews.full_review_text_ingested,
        "sample_reviews": [
            {
                "content": excerpt(review.content, 300),
                "rating": review.rating,
                "author": review.author,
                "verified_buyer": review.verified_buyer,
            }
            for review in p.reviews.items[:3]
        ],
    }
    return {
        "title": p.title,
        "vendor": p.vendor,
        "product_type": p.product_type,
        "description": excerpt(p.description_text, 1200),
        "benefits": p.benefits,
        "ingredients_raw": excerpt(p.ingredients_raw, 800),
        "ingredient_groups": {k: v for k, v in p.ingredient_groups.items()},
        "suggested_use": excerpt(p.suggested_use, 400),
        "warnings": p.warnings,
        "one_time_price": p.one_time_price.formatted if p.one_time_price else None,
        "subscription_price": p.subscription_price.formatted if p.subscription_price else None,
        "subscription_savings_percent": p.subscription_savings_percent,
        "available": p.available,
        "variants": [v.title for v in p.variants if v.title],
        "reviews": review_facts,
        "image_count": len(p.images),
        "image_alt_coverage": round(sum(1 for i in p.images if i.alt_text) / len(p.images), 2) if p.images else 0,
        "seo_title": p.seo.title,
        "seo_description": p.seo.description,
        "extraction_warnings": p.extraction_warnings,
    }
