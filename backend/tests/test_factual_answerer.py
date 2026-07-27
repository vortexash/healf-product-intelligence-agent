from datetime import datetime, timezone

from app.intelligence import factual_answerer as fa
from app.intelligence.intent_router import classify
from app.models import Money, ProductData, ProductImage, ReviewSummary, SellingPlan


def _product(**kw):
    base = dict(
        source_url="u", handle="h", retrieved_at=datetime.now(timezone.utc),
    )
    base.update(kw)
    return ProductData(**base)


def test_ingredient_present_with_alias():
    p = _product(ingredients_raw="Salt, Magnesium Malate, Potassium Chloride")
    a = fa.answer_ingredient(p, "magnesium")
    assert "is listed" in a.text.lower()
    assert a.confidence == "high"


def test_ingredient_alias_cholecalciferol():
    p = _product(ingredients_raw="Cholecalciferol, Water")
    a = fa.answer_ingredient(p, "Vitamin D")
    assert "is listed" in a.text.lower()


def test_ingredient_not_listed_wording():
    p = _product(ingredients_raw="Salt, Citric Acid")
    a = fa.answer_ingredient(p, "Vitamin D")
    assert "not listed" in a.text.lower()
    assert "does not contain" not in a.text.lower()


def test_ingredient_unknown_when_no_section():
    p = _product()
    a = fa.answer_ingredient(p, "Vitamin D")
    assert a.confidence == "low"
    assert "unknown" in a.text.lower()


def test_reviews_present():
    p = _product(reviews=ReviewSummary(present=True, count=516, average_rating=4.9))
    a = fa.answer_reviews(p)
    assert "516" in a.text
    assert "4.9" in a.text
    assert any("individual review" in l.lower() for l in a.limitations)


def test_reviews_unknown():
    p = _product(reviews=ReviewSummary())
    a = fa.answer_reviews(p)
    assert a.confidence == "low"


def test_price_with_subscription():
    p = _product(
        one_time_price=Money(amount=18.99, formatted="£18.99"),
        subscription_price=Money(amount=17.09, formatted="£17.09"),
        subscription_savings_percent=10.0,
        available=True,
    )
    a = fa.answer_price(p)
    assert "£18.99" in a.text and "£17.09" in a.text


def test_intent_routing():
    assert classify("Does this product have any reviews?").intent == "review_lookup"
    assert classify("Does it contain Vitamin D?").intent == "ingredient_lookup"
    assert classify("Is it in stock?").intent == "availability_lookup"
    assert classify("What can I improve on this page?").intent == "page_evaluation"
    assert classify("Rewrite the description").intent == "content_rewrite"
    assert classify("Create an FAQ").intent == "faq_generation"


def test_ingredient_target_extraction():
    r = classify("Does it contain Vitamin D?")
    assert r.target_entity and "vitamin d" in r.target_entity.lower()
