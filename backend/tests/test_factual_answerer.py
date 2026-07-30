from datetime import datetime, timezone

from app.intelligence import factual_answerer as fa
from app.intelligence.intent_router import classify
from app.models import Money, ProductData, ProductImage, ProductReview, ReviewSummary, SellingPlan


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


def test_individual_review_request_without_text_is_honest():
    p = _product(reviews=ReviewSummary(present=True, count=522, average_rating=4.9))
    a = fa.answer_reviews(p, "pull any one review")
    assert "can't pull an individual written review" in a.text.lower()
    assert "does not expose the customer review text" in a.text.lower()
    assert "won't generate or paraphrase" in a.text.lower()
    assert "522" in a.text and "4.9" in a.text
    assert not a.text.startswith("**Yes, this product has reviews.**")


def test_individual_review_request_returns_real_embedded_review():
    p = _product(
        reviews=ReviewSummary(
            present=True,
            count=522,
            average_rating=4.9,
            full_review_text_ingested=True,
            items=[
                ProductReview(
                    id="1",
                    content="Taste is great- No junk in the ingredients.",
                    rating=5,
                    author="Zann B.",
                    verified_buyer=True,
                )
            ],
        )
    )
    a = fa.answer_reviews(p, "pull any one review")
    assert "sure - here's one" in a.text.lower()
    assert "Taste is great- No junk in the ingredients." in a.text
    assert "Zann B." in a.text
    assert "5/5" in a.text
    assert "Verified buyer" in a.text
    assert "can't pull" not in a.text.lower()
    assert a.limitations == []


def test_review_quantity_and_followup_continue_without_repeating():
    reviews = [
        ProductReview(id=str(index), content=f"Review number {index}.", rating=5)
        for index in range(1, 6)
    ]
    p = _product(
        reviews=ReviewSummary(
            present=True,
            count=5,
            average_rating=5,
            full_review_text_ingested=True,
            items=reviews,
        )
    )

    first = fa.answer_reviews(p, "give 3 reviews")
    assert "here are 3 reviews" in first.text.lower()
    assert "Review number 1." in first.text
    assert "Review number 2." in first.text
    assert "Review number 3." in first.text
    assert "Review number 4." not in first.text

    followup = fa.answer_reviews(p, "another one", ["give 3 reviews"])
    assert "Review number 4." in followup.text
    assert "Review number 1." not in followup.text


def test_top_five_review_typo_singular_is_ranked():
    reviews = [
        ProductReview(id="low", content="Lower rated.", rating=3, votes_up=100),
        ProductReview(id="fifth", content="Fifth best.", rating=4, votes_up=1),
        ProductReview(id="fourth", content="Fourth best.", rating=5, votes_up=1),
        ProductReview(id="third", content="Third best.", rating=5, votes_up=3),
        ProductReview(id="second", content="Second best.", rating=5, votes_up=5),
        ProductReview(id="first", content="First best.", rating=5, votes_up=10),
    ]
    p = _product(
        reviews=ReviewSummary(
            present=True,
            count=6,
            average_rating=4.5,
            full_review_text_ingested=True,
            items=reviews,
        )
    )

    answer = fa.answer_reviews(p, "give nme the top 5 review")

    assert "here are the top 5 reviews" in answer.text.lower()
    assert answer.text.count('> "') == 5
    assert answer.text.index("First best.") < answer.text.index("Second best.")
    assert answer.text.index("Second best.") < answer.text.index("Third best.")
    assert "Lower rated." not in answer.text


def test_individual_review_markdown_is_escaped():
    p = _product(
        reviews=ReviewSummary(
            present=True,
            full_review_text_ingested=True,
            items=[
                ProductReview(
                    content="Great [offer](https://example.com) and *results*.",
                    rating=5,
                )
            ],
        )
    )
    a = fa.answer_reviews(p, "show one review")
    assert r"\[offer\](https://example.com)" in a.text
    assert r"\*results\*" in a.text


def test_rating_question_still_returns_aggregate_answer():
    p = _product(reviews=ReviewSummary(present=True, count=522, average_rating=4.9))
    a = fa.answer_reviews(p, "What is the rating?")
    assert a.text.startswith("It has")
    assert "522" in a.text and "4.9" in a.text


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
