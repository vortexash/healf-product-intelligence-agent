from datetime import datetime, timezone

from app.intelligence import content_generator
from app.models import ProductData, ReviewSummary


async def test_generated_copy_does_not_turn_review_count_into_happy_customers(monkeypatch):
    monkeypatch.setattr("app.intelligence.llm_client.is_configured", lambda: True)

    async def generated_response(system, user, **kwargs):
        return {
            "title": "Draft",
            "content": (
                "Banish fatigue with a precise blend. Rated 4.9 out of 5 stars by 523 happy customers.\n\n"
                '> *"A slightly rewritten review."* - Verified Buyer'
            ),
            "facts_used": ["523 reviews", "4.9/5"],
            "claims_preserved": [],
            "claims_not_introduced": ["medical claims"],
        }

    monkeypatch.setattr("app.intelligence.llm_client.complete_json", generated_response)
    product = ProductData(
        source_url="https://healf.com/products/example",
        handle="example",
        retrieved_at=datetime.now(timezone.utc),
        title="Example Electrolytes",
        reviews=ReviewSummary(present=True, count=523, average_rating=4.9),
    )

    draft = await content_generator.generate(product, "content_rewrite", "Rewrite it")

    assert "523 reviews" in draft.content
    assert "happy customers" not in draft.content
    assert "rewritten review" not in draft.content
    assert "Banish fatigue" not in draft.content
    assert "## Example Electrolytes" in draft.content
