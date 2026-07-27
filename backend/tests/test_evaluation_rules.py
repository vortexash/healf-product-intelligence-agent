from datetime import datetime, timezone

from app.intelligence.evaluation_rules import build_scorecard, compute_signals
from app.models import Money, ProductData, ProductImage, ReviewSummary


def _product(**kw):
    base = dict(source_url="u", handle="h", retrieved_at=datetime.now(timezone.utc))
    base.update(kw)
    return ProductData(**base)


def test_empty_product_scores_low():
    cats, overall, _ = build_scorecard(_product())
    assert overall < 40
    by = {c.key: c for c in cats}
    assert by["ingredients"].score == 0
    assert by["images"].score == 0


def test_missing_description_flagged():
    cats, _, _ = build_scorecard(_product())
    desc = next(c for c in cats if c.key == "description")
    assert any("description" in f.lower() for f in desc.findings)


def test_low_image_and_alt_flagged():
    p = _product(images=[ProductImage(url="https://x/a.png")])
    cats, _, _ = build_scorecard(p)
    img = next(c for c in cats if c.key == "images")
    assert any("alt-text" in f.lower() for f in img.findings)
    assert any("image" in f.lower() for f in img.findings)


def test_strong_product_scores_high():
    p = _product(
        title="X",
        vendor="Acme",
        description_text=("word " * 220).strip() + "\n\nsecond paragraph here.",
        benefits=["a", "b"],
        suggested_use="use it",
        ingredients_raw="Salt, Water, Sugar and more listed here",
        ingredient_groups={"Citrus": ["Salt"], "Berry": ["Sugar"]},
        warnings=["Keep away from children"],
        one_time_price=Money(amount=18.99),
        subscription_price=Money(amount=17.0),
        subscription_savings_percent=10.0,
        available=True,
        images=[ProductImage(url=f"https://x/{i}.png", alt_text="alt") for i in range(5)],
        reviews=ReviewSummary(present=True, count=500, average_rating=4.9),
    )
    p.seo.title = "Acme X Electrolytes Variety Pack Supplement"
    p.seo.description = "Buy Acme X at Healf. A great electrolyte mix for everyday hydration and balance today."
    p.seo.canonical_url = "https://healf.com/products/x"
    cats, overall, _ = build_scorecard(p)
    assert overall >= 80


def test_signals_shape():
    s = compute_signals(_product(images=[ProductImage(url="a", alt_text="x")]))
    assert s["images"]["alt_coverage"] == 1.0
    assert "description" in s and "seo" in s
