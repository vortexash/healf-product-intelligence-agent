from datetime import datetime, timezone

from app.intelligence import evaluator
from app.models import ProductData, ProductReview, ReviewSummary, SourceEvidence


def _product(*, description: str = "An electrolyte variety pack.") -> ProductData:
    url = "https://healf.com/en-uk/products/lmnt"
    return ProductData(
        source_url=url,
        handle="lmnt",
        retrieved_at=datetime.now(timezone.utc),
        title="Recharge Electrolytes - Variety Pack",
        description_text=description,
        reviews=ReviewSummary(
            present=True,
            count=522,
            average_rating=4.9,
            full_review_text_ingested=False,
        ),
        evidence=[
            SourceEvidence(
                field="description_text",
                source_type="html",
                source_url=url,
                excerpt=description,
                confidence=0.9,
            ),
            SourceEvidence(
                field="reviews",
                source_type="json_ld",
                source_url=url,
                excerpt="rating=4.9 count=522",
                confidence=0.9,
            ),
        ],
    )


async def test_evaluation_replaces_unsupported_health_diet_and_review_copy(monkeypatch):
    monkeypatch.setattr("app.intelligence.llm_client.is_configured", lambda: True)
    monkeypatch.setattr("app.intelligence.evaluator.load_benchmark", lambda: None)

    async def unsafe_response(system, user, **kwargs):
        return {
            "summary": "A gluten-free electrolyte made for heart health.",
            "recommendations": [
                {
                    "priority": 1,
                    "title": "Include Allergen and Dietary Information",
                    "rationale": "Health shoppers need reassurance.",
                    "suggested_action": (
                        "Add: 'This product is gluten-free and keto-friendly. "
                        "Contains no common allergens.'"
                    ),
                    "evidence_fields": ["ingredients_raw", "made_up_field"],
                },
                {
                    "priority": 2,
                    "title": "Feature a Standout Review",
                    "rationale": "The 522 reviews are strong social proof.",
                    "suggested_action": (
                        "Highlight: 'The variety supports my intense workout routine.'"
                    ),
                    "evidence_fields": ["reviews"],
                },
                {
                    "priority": 3,
                    "title": "Explain Electrolyte Benefits",
                    "rationale": "Help active shoppers understand the formula.",
                    "suggested_action": (
                        "Add: 'Potassium supports heart and muscle function during "
                        "high-intensity workouts.'"
                    ),
                    "evidence_fields": ["description_text"],
                },
                {
                    "priority": 4,
                    "title": "Ensure Allergen Information Availability",
                    "rationale": "Dietary shoppers need verified information.",
                    "suggested_action": (
                        "Verify allergen content with the supplier and publish confirmed details."
                    ),
                    "evidence_fields": [],
                },
            ],
            "limitations": [],
        }

    monkeypatch.setattr("app.intelligence.llm_client.complete_json", unsafe_response)

    result = await evaluator.evaluate(_product(), "What can I improve?")
    output = " ".join(
        [result.summary]
        + [
            f"{rec.title} {rec.rationale} {rec.suggested_action}"
            for rec in result.recommendations
        ]
    ).lower()

    assert "gluten-free" not in output
    assert "keto-friendly" not in output
    assert "contains no common allergens" not in output
    assert "supports my intense workout routine" not in output
    assert "supports heart and muscle function" not in output
    assert "verify allergen and dietary information" in output
    assert "choose a real, permissioned customer quote" in output
    assert "substantiate product-benefit copy" in output
    assert len(result.recommendations) == 3
    assert [rec.priority for rec in result.recommendations] == [1, 2, 3]
    assert any("verification-first" in limitation for limitation in result.limitations)
    assert all("made_up_field" not in rec.evidence_fields for rec in result.recommendations)


async def test_supported_dietary_claim_is_not_removed(monkeypatch):
    monkeypatch.setattr("app.intelligence.llm_client.is_configured", lambda: True)
    monkeypatch.setattr("app.intelligence.evaluator.load_benchmark", lambda: None)

    async def grounded_response(system, user, **kwargs):
        return {
            "summary": "The page identifies the product as vegan and gluten-free.",
            "recommendations": [
                {
                    "priority": 1,
                    "title": "Surface verified dietary information",
                    "rationale": "The description already confirms these attributes.",
                    "suggested_action": "Add a visible 'Vegan and gluten-free' line.",
                    "evidence_fields": ["description_text"],
                }
            ],
            "limitations": [],
        }

    monkeypatch.setattr("app.intelligence.llm_client.complete_json", grounded_response)
    result = await evaluator.evaluate(
        _product(description="This electrolyte mix is vegan and gluten-free."),
        "What can I improve?",
    )

    assert result.recommendations[0].title == "Surface verified dietary information"
    assert "Vegan and gluten-free" in result.recommendations[0].suggested_action
    assert not any("verification-first" in limitation for limitation in result.limitations)


async def test_review_count_in_rationale_does_not_replace_unrelated_action(monkeypatch):
    monkeypatch.setattr("app.intelligence.llm_client.is_configured", lambda: True)
    monkeypatch.setattr("app.intelligence.evaluator.load_benchmark", lambda: None)

    async def grounded_response(system, user, **kwargs):
        return {
            "summary": "The description is shorter than comparable pages.",
            "recommendations": [
                {
                    "priority": 1,
                    "title": "Expand the product description",
                    "rationale": "Despite strong reviews, the description is short.",
                    "suggested_action": "Add verified preparation and usage details.",
                    "evidence_fields": ["description_text"],
                }
            ],
            "limitations": [],
        }

    monkeypatch.setattr("app.intelligence.llm_client.complete_json", grounded_response)
    result = await evaluator.evaluate(_product(), "What can I improve?")

    assert result.recommendations[0].title == "Expand the product description"
    assert result.recommendations[0].suggested_action == "Add verified preparation and usage details."


async def test_review_recommendation_uses_ingested_quote_not_generated_copy(monkeypatch):
    monkeypatch.setattr("app.intelligence.llm_client.is_configured", lambda: True)
    monkeypatch.setattr("app.intelligence.evaluator.load_benchmark", lambda: None)

    async def response_with_fake_quote(system, user, **kwargs):
        return {
            "summary": "The product has strong aggregate review evidence.",
            "recommendations": [
                {
                    "priority": 1,
                    "title": "Feature a customer review",
                    "rationale": "Social proof can help shoppers.",
                    "suggested_action": "Add: 'This completely changed my workouts.'",
                    "evidence_fields": ["reviews"],
                }
            ],
            "limitations": [],
        }

    monkeypatch.setattr("app.intelligence.llm_client.complete_json", response_with_fake_quote)
    product = _product()
    product.reviews.full_review_text_ingested = True
    product.reviews.items = [
        ProductReview(
            content="Taste is great- No junk in the ingredients.",
            rating=5,
            author="Zann B.",
            verified_buyer=True,
        )
    ]

    result = await evaluator.evaluate(product, "What can I improve?")
    action = result.recommendations[0].suggested_action
    assert "Taste is great- No junk in the ingredients." in action
    assert "This completely changed my workouts." not in action
    assert "Zann B." in action
