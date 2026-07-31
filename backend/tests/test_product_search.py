from datetime import datetime, timezone

import pytest

from app.intelligence import product_search, response_composer
from app.intelligence.product_search import ProductSuggestion
from app.models import Money, ProductData, ReviewSummary


@pytest.fixture
def electrolyte_product() -> ProductData:
    return ProductData(
        source_url="https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack",
        retrieved_at=datetime.now(timezone.utc),
        handle="lmnt-recharge-electrolytes-variety-pack",
        title="Recharge Electrolytes - Variety Pack",
        vendor="LMNT",
        product_type="Vitamins & Supplements",
        one_time_price=Money(amount=18.99, currency="GBP", formatted="£18.99"),
    )


def test_derive_search_query_uses_current_product_topic(electrolyte_product):
    assert product_search.derive_search_query(electrolyte_product, "similar items") == "electrolyte"


def test_derive_search_query_prefers_explicit_requested_topic(electrolyte_product):
    assert (
        product_search.derive_search_query(
            electrolyte_product, "Can you suggest some magnesium products instead?"
        )
        == "magnesium"
    )


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Do you have any protein bars?", "protein bar"),
        ("Do you have any collagen powder?", "collagen powder"),
        ("Do you have any sleep masks?", "sleep mask"),
        ("Do you have any shampoo?", "shampoo"),
        ("Do you have any red light therapy devices?", "red light therapy devices"),
    ],
)
def test_derive_discovery_query_understands_natural_category_question(question, expected):
    assert product_search.derive_discovery_query(question) == expected


async def test_discover_returns_live_category_matches(monkeypatch):
    async def fake_search(query, first):
        assert query == "protein bar"
        return [
            ProductSuggestion(
                title="Chocolate Protein Bar",
                vendor="Brand A",
                handle="chocolate-protein-bar",
                price="£2.99",
                available=True,
                price_amount=2.99,
            ),
            ProductSuggestion(
                title="Protein Powder",
                vendor="Brand B",
                handle="protein-powder",
                price="£29.99",
                available=True,
                price_amount=29.99,
            ),
        ]

    monkeypatch.setattr(product_search, "_search_catalog", fake_search)
    text, suggestions, evidence, query = await product_search.discover(
        "Do you have any protein bars?"
    )

    assert query == "protein bar"
    assert [item.handle for item in suggestions] == ["chocolate-protein-bar"]
    assert "Chocolate Protein Bar" in text
    assert len(evidence) == 1


async def test_discover_rejects_unrelated_catalog_results(monkeypatch):
    async def fake_search(query, first):
        assert query == "sleep mask"
        return [
            ProductSuggestion(
                title="Menstrual Cup B",
                vendor="Mooncup",
                handle="menstrual-cup-b",
                price="£23.50",
                available=True,
            ),
            ProductSuggestion(
                title="Pure Silk Sleep Mask",
                vendor="Slip",
                handle="pure-silk-sleep-mask",
                price="£50.00",
                available=True,
            ),
        ]

    monkeypatch.setattr(product_search, "_search_catalog", fake_search)
    _, suggestions, _, query = await product_search.discover("Do you have any sleep masks?")

    assert query == "sleep mask"
    assert [item.handle for item in suggestions] == ["pure-silk-sleep-mask"]


def test_parse_public_storefront_config():
    html = (
        'self.__next_f.push([1,"store config: '
        '\\"store\\":{\\"url\\":\\"https://how2go.myshopify.com/api/2026-01/graphql.json\\",'
        '\\"token\\":\\"public-token\\"}"])'
    )
    assert product_search._parse_storefront_config(html) == (
        "https://how2go.myshopify.com/api/2026-01/graphql.json",
        "public-token",
    )


async def test_recommend_returns_live_catalog_links(monkeypatch, electrolyte_product):
    async def fake_search(query, first):
        assert query == "electrolyte"
        assert first >= 12
        return [
            ProductSuggestion(
                title="Current LMNT product",
                vendor="LMNT",
                handle=electrolyte_product.handle,
                price="£18.99",
                available=True,
            ),
            ProductSuggestion(
                title="Everyday Hydration Salts",
                vendor="Sodii",
                handle="everyday-hydration-salts",
                price="£32.49",
                available=True,
            ),
            ProductSuggestion(
                title="Unrelated Sleep Mask",
                vendor="Other",
                handle="sleep-mask",
                price="£10.00",
                available=True,
            ),
            ProductSuggestion(
                title="Electrolytes Concentrate Mini",
                vendor="Oshun",
                handle="electrolytes-concentrate-mini",
                price="£20.00",
                available=True,
            ),
        ]

    monkeypatch.setattr(product_search, "_search_catalog", fake_search)
    text, suggestions, evidence = await product_search.recommend(
        electrolyte_product, "similar items"
    )

    assert [item.handle for item in suggestions] == [
        "everyday-hydration-salts",
        "electrolytes-concentrate-mini",
    ]
    assert "[Everyday Hydration Salts](https://healf.com/en-uk/products/everyday-hydration-salts)" in text
    assert "not personalised medical recommendations" in text
    assert len(evidence) == 2


async def test_recommend_honours_price_limit(monkeypatch, electrolyte_product):
    async def fake_search(query, first):
        return [
            ProductSuggestion(
                title="Electrolyte Powder Budget",
                vendor="Brand A",
                handle="electrolyte-budget",
                price="£19.99",
                available=True,
                price_amount=19.99,
            ),
            ProductSuggestion(
                title="Electrolyte Powder Premium",
                vendor="Brand B",
                handle="electrolyte-premium",
                price="£39.99",
                available=True,
                price_amount=39.99,
            ),
        ]

    monkeypatch.setattr(product_search, "_search_catalog", fake_search)
    text, suggestions, _ = await product_search.recommend(
        electrolyte_product, "Show me electrolyte options under £20"
    )

    assert [item.handle for item in suggestions] == ["electrolyte-budget"]
    assert "under **£20**" in text


def test_recommendation_followups_are_contextual_and_non_redundant(electrolyte_product):
    prompts = response_composer.suggest_follow_ups(
        electrolyte_product,
        "product_recommendation",
        current_message="similar items",
        prior_user_messages=["Can you suggest me other products?"],
    )

    assert prompts == [
        "Show me electrolyte options under £20",
        "Show me electrolyte options from a different brand",
        "What should I compare before choosing?",
    ]
    assert all("ingredients" not in prompt.lower() for prompt in prompts)
    assert all("rewrite" not in prompt.lower() for prompt in prompts)


def test_summary_followups_name_product_and_go_deeper(electrolyte_product):
    detailed = electrolyte_product.model_copy(
        update={
            "warnings": ["Consult a healthcare professional if needed."],
            "ingredients_raw": "Sodium, magnesium, potassium",
            "reviews": ReviewSummary(present=True, count=523, average_rating=4.9),
            "subscription_price": Money(amount=17.09, currency="GBP", formatted="£17.09"),
        }
    )
    prompts = response_composer.suggest_follow_ups(
        detailed,
        "product_summary",
        current_message="Tell me about the first one",
        prior_user_messages=["Can you suggest other products?"],
    )

    assert prompts == [
        "What warnings are listed for Recharge Electrolytes?",
        "Are any allergens listed for Recharge Electrolytes?",
        "How strong is the review evidence for Recharge Electrolytes?",
    ]
    assert "What can I improve on this page?" not in prompts


async def test_find_product_url_matches_vendor_and_title(monkeypatch):
    async def fake_search(query, first):
        assert query == "arrae magnesium"
        return [
            ProductSuggestion(
                title="Magnesium",
                vendor="Arrae",
                handle="arrae-magnesium",
                price="£38.99",
                available=True,
            ),
            ProductSuggestion(
                title="Magnesium+",
                vendor="Heights",
                handle="heights-magnesium",
                price="£27.00",
                available=True,
            ),
        ]

    monkeypatch.setattr(product_search, "_search_catalog", fake_search)
    assert await product_search.find_product_url("Arrae Magnesium") == (
        "https://healf.com/en-uk/products/arrae-magnesium"
    )
