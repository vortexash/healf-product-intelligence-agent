import json
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app import chat_service
from app.intelligence import evaluator, response_composer
from app.intelligence.product_search import ProductSuggestion
from app.main import app
from app.models import ProductData, SourceEvidence
from app.navigation.healf_client import FetchResult


@pytest.fixture(autouse=True)
def offline(monkeypatch, lmnt_html, source_url):
    """Serve the saved fixture instead of hitting the network; no LLM by default."""
    async def fake_fetch(url):
        return FetchResult(url=source_url, status=200, text=lmnt_html, content_type="text/html")

    async def no_json(url):
        return None

    monkeypatch.setattr("app.ingestion.ingest.fetch", fake_fetch)
    monkeypatch.setattr("app.ingestion.shopify_parser.try_fetch_json", no_json)
    # fresh caches/sessions per test
    from app.context import product_cache, sessions as store

    product_cache._store.clear()
    store._sessions.clear()


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_health():
    async with await _client() as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_fetch_endpoint(source_url):
    async with await _client() as c:
        r = await c.post("/api/products/fetch", json={"url": source_url})
    assert r.status_code == 200
    p = r.json()["product"]
    assert p["title"].startswith("Recharge")
    assert p["reviews"]["count"] == 516


async def test_chat_ingredient_and_followup(source_url):
    async with await _client() as c:
        # First message: URL + question.
        r1 = await c.post("/api/chat", json={"message": f"{source_url}\nDoes it contain Vitamin D?"})
        d1 = r1.json()
        assert d1["answer"]["intent"] == "ingredient_lookup"
        assert "not listed" in d1["answer"]["text"].lower()
        assert d1["product"]["title"].startswith("Recharge")
        sid = d1["session_id"]

        # Follow-up WITHOUT the URL - uses session context.
        r2 = await c.post("/api/chat", json={"session_id": sid, "message": "How many reviews does it have?"})
        d2 = r2.json()
    assert d2["answer"]["intent"] == "review_lookup"
    assert "516" in d2["answer"]["text"]
    assert d2["product"]["title"].startswith("Recharge")


async def test_chat_review_requests_are_conversational(source_url):
    async with await _client() as c:
        first = await c.post(
            "/api/chat",
            json={"message": f"{source_url}\npull any one review"},
        )
        data = first.json()
        sid = data["session_id"]
        three = await c.post(
            "/api/chat",
            json={"session_id": sid, "message": "give 3 reviews"},
        )
        another = await c.post(
            "/api/chat",
            json={"session_id": sid, "message": "another one"},
        )
        next_one = await c.post(
            "/api/chat",
            json={"session_id": sid, "message": "next"},
        )

    assert first.status_code == 200
    assert data["answer"]["intent"] == "review_lookup"
    assert "sure - here's one" in data["answer"]["text"].lower()
    assert "Taste is great- No junk in the ingredients." in data["answer"]["text"]
    assert data["answer"]["limitations"] == []
    assert data["product"]["reviews"]["full_review_text_ingested"] is True
    assert len(data["product"]["reviews"]["items"]) == 10
    assert len(data["evidence"]) == 2
    assert data["suggested_actions"] == [
        "Show me 3 reviews for Recharge Electrolytes",
        "Show the latest review for Recharge Electrolytes",
        "What is the average rating for Recharge Electrolytes?",
    ]

    three_data = three.json()
    assert three.status_code == 200
    assert "here are 3 reviews" in three_data["answer"]["text"].lower()
    assert three_data["answer"]["text"].count('> "') == 3
    assert "Taste is great- No junk in the ingredients." not in three_data["answer"]["text"]
    assert three_data["answer"]["limitations"] == []

    another_data = another.json()
    assert another.status_code == 200
    assert another_data["answer"]["intent"] == "review_lookup"
    assert "sure - here's one" in another_data["answer"]["text"].lower()

    next_data = next_one.json()
    assert next_one.status_code == 200
    assert next_data["answer"]["intent"] == "review_lookup"
    assert "sure - here's one" in next_data["answer"]["text"].lower()


async def test_no_active_product_gets_conversational_onboarding():
    async with await _client() as c:
        r = await c.post("/api/chat", json={"message": "Hi, what can you help me with?"})
    data = r.json()
    assert r.status_code == 200
    assert data["answer"]["intent"] == "product_onboarding"
    assert "Healf product URL" in data["answer"]["text"]
    assert data["product"] is None


async def test_catalog_question_works_without_active_product(monkeypatch):
    suggestion = ProductSuggestion(
        title="Chocolate Protein Bar",
        vendor="Test Brand",
        handle="chocolate-protein-bar",
        price="£2.99",
        available=True,
    )
    evidence = SourceEvidence(
        field="product_recommendation",
        source_type="derived",
        source_url=suggestion.url,
        excerpt="Chocolate Protein Bar · Test Brand · £2.99",
        selector="Healf Storefront catalog search",
        confidence=0.9,
    )

    async def fake_discover(message, limit=4):
        assert message == "Do you have any protein bars?"
        return (
            f"Yes - try [{suggestion.title}]({suggestion.url}).",
            [suggestion],
            [evidence],
            "protein bar",
        )

    monkeypatch.setattr(response_composer.product_search, "discover", fake_discover)
    async with await _client() as c:
        response = await c.post(
            "/api/chat",
            json={"message": "Do you have any protein bars?"},
        )

    data = response.json()
    assert response.status_code == 200
    assert data["answer"]["intent"] == "product_recommendation"
    assert "Chocolate Protein Bar" in data["answer"]["text"]
    assert data["product"] is None
    assert data["suggested_actions"] == [
        "Tell me about the first one",
        "Show me protein bar options under £30",
    ]


async def test_similar_products_uses_catalog_recommendation_intent(monkeypatch, source_url):
    async def fake_recommend(product, message, limit=4):
        suggestion = ProductSuggestion(
            title="Everyday Hydration Salts",
            vendor="Sodii",
            handle="everyday-hydration-salts",
            price="£32.49",
            available=True,
        )
        evidence = SourceEvidence(
            field="product_recommendation",
            source_type="derived",
            source_url=suggestion.url,
            excerpt="Everyday Hydration Salts · Sodii · £32.49",
            selector="Healf Storefront catalog search",
            confidence=0.9,
        )
        return (
            f"Try [{suggestion.title}]({suggestion.url}) - Sodii · £32.49",
            [suggestion],
            [evidence],
        )

    monkeypatch.setattr(response_composer.product_search, "recommend", fake_recommend)
    async with await _client() as c:
        response = await c.post(
            "/api/chat",
            json={"message": f"{source_url}\nCan you suggest me other products?"},
        )

    data = response.json()
    assert response.status_code == 200
    assert data["answer"]["intent"] == "product_recommendation"
    assert "Everyday Hydration Salts" in data["answer"]["text"]
    assert data["evidence"][0]["field"] == "product_recommendation"
    assert data["suggested_actions"] == [
        "Show me electrolyte options under £20",
        "Show me electrolyte options from a different brand",
        "What should I compare before choosing?",
    ]


async def test_similar_products_recovers_product_from_browser_history(monkeypatch, source_url):
    async def fake_recommend(product, message, limit=4):
        return ("A live catalog match.", [], [])

    monkeypatch.setattr(response_composer.product_search, "recommend", fake_recommend)
    browser_history = [
        {"role": "user", "text": f"{source_url}\nTell me about this product"},
        {"role": "assistant", "text": "It is an electrolyte variety pack."},
    ]
    async with await _client() as c:
        response = await c.post(
            "/api/chat",
            json={
                "session_id": "browser-tab-after-backend-restart",
                "message": "similar items",
                "history": browser_history,
            },
        )

    data = response.json()
    assert response.status_code == 200
    assert data["answer"]["intent"] == "product_recommendation"
    assert data["product"]["handle"] == "lmnt-recharge-electrolytes-variety-pack"


async def test_product_name_from_recommendations_switches_active_product(monkeypatch, source_url):
    everyday_url = (
        "https://healf.com/en-uk/products/"
        "everyday-hydration-salts-salty-chocolate-sachet-30-serves"
    )

    async def fake_ingest(parsed):
        is_everyday = parsed.handle.startswith("everyday-hydration-salts")
        return ProductData(
            source_url=parsed.normalized_url,
            retrieved_at=datetime.now(timezone.utc),
            handle=parsed.handle,
            title=(
                "Everyday Hydration Salts - Salty Chocolate"
                if is_everyday
                else "Recharge Electrolytes - Variety Pack"
            ),
            vendor="Sodii" if is_everyday else "LMNT",
        )

    async def fake_recommend(product, message, limit=4):
        return (
            f"1. [Everyday Hydration Salts - Salty Chocolate]({everyday_url}) - Sodii · £32.49",
            [],
            [],
        )

    monkeypatch.setattr(chat_service, "ingest_product", fake_ingest)
    monkeypatch.setattr(response_composer.product_search, "recommend", fake_recommend)
    monkeypatch.setattr(response_composer.llm_client, "is_configured", lambda: False)

    async with await _client() as c:
        recommendations = await c.post(
            "/api/chat",
            json={"message": f"{source_url}\nCan you suggest me other products?"},
        )
        session_id = recommendations.json()["session_id"]
        named = await c.post(
            "/api/chat",
            json={
                "session_id": session_id,
                "message": "Can you tell me about Everyday Hydration Salts - Salty Chocolate?",
            },
        )
        ordinal = await c.post(
            "/api/chat",
            json={"session_id": session_id, "message": "Tell me about the first one"},
        )

    named_data = named.json()
    assert named.status_code == 200
    assert named_data["product"]["handle"].startswith("everyday-hydration-salts")
    assert named_data["product"]["vendor"] == "Sodii"
    assert "Everyday Hydration Salts" in named_data["answer"]["text"]
    assert "LMNT" not in named_data["answer"]["text"]

    ordinal_data = ordinal.json()
    assert ordinal.status_code == 200
    assert ordinal_data["product"]["handle"].startswith("everyday-hydration-salts")


async def test_arbitrary_named_product_switch_uses_catalog_and_summarizes(monkeypatch, source_url):
    arrae_url = "https://healf.com/en-uk/products/arrae-magnesium"

    async def fake_ingest(parsed):
        is_arrae = parsed.handle == "arrae-magnesium"
        return ProductData(
            source_url=parsed.normalized_url,
            retrieved_at=datetime.now(timezone.utc),
            handle=parsed.handle,
            title="Magnesium" if is_arrae else "Recharge Electrolytes - Variety Pack",
            vendor="Arrae" if is_arrae else "LMNT",
        )

    async def fake_find(name):
        assert name == "Arrae Magnesium"
        return arrae_url

    monkeypatch.setattr(chat_service, "ingest_product", fake_ingest)
    monkeypatch.setattr(chat_service.product_search, "find_product_url", fake_find)
    monkeypatch.setattr(response_composer.llm_client, "is_configured", lambda: False)

    async with await _client() as c:
        first = await c.post(
            "/api/chat",
            json={"message": f"{source_url}\nSummarize this product"},
        )
        switched = await c.post(
            "/api/chat",
            json={
                "session_id": first.json()["session_id"],
                "message": "Tell me about Arrae Magnesium",
            },
        )

    data = switched.json()
    assert switched.status_code == 200
    assert data["product"]["handle"] == "arrae-magnesium"
    assert data["answer"]["intent"] == "product_summary"
    assert "**Magnesium** by Arrae" in data["answer"]["text"]


async def test_named_product_switch_overrides_stale_browser_product_url(monkeypatch):
    everyday_url = "https://healf.com/en-uk/products/everyday-hydration-salts"
    oshun_url = "https://healf.com/en-uk/products/electrolytes-concentrate-mini"

    async def fake_ingest(parsed):
        is_oshun = parsed.handle == "electrolytes-concentrate-mini"
        return ProductData(
            source_url=parsed.normalized_url,
            retrieved_at=datetime.now(timezone.utc),
            handle=parsed.handle,
            title=("Electrolytes Concentrate Mini" if is_oshun else "Everyday Hydration Salts"),
            vendor="Oshun" if is_oshun else "Sodii",
        )

    async def fake_find(name):
        assert name == "Electrolytes Concentrate Mini"
        return oshun_url

    monkeypatch.setattr(chat_service, "ingest_product", fake_ingest)
    monkeypatch.setattr(chat_service.product_search, "find_product_url", fake_find)
    monkeypatch.setattr(response_composer.llm_client, "is_configured", lambda: False)

    async with await _client() as c:
        switched = await c.post(
            "/api/chat",
            json={
                "message": "Tell me about Electrolytes Concentrate Mini",
                "product_url": everyday_url,
            },
        )
        follow_up = await c.post(
            "/api/chat",
            json={
                "session_id": switched.json()["session_id"],
                "message": "Compare one-time vs subscription pricing",
                "product_url": oshun_url,
            },
        )

    switched_data = switched.json()
    assert switched_data["product"]["handle"] == "electrolytes-concentrate-mini"
    assert switched_data["product"]["vendor"] == "Oshun"
    assert follow_up.json()["product"]["handle"] == "electrolytes-concentrate-mini"


async def test_product_url_slug_does_not_pollute_intent(monkeypatch):
    arrae_url = "https://healf.com/en-uk/products/arrae-magnesium"

    async def fake_ingest(parsed):
        return ProductData(
            source_url=parsed.normalized_url,
            retrieved_at=datetime.now(timezone.utc),
            handle=parsed.handle,
            title="Magnesium",
            vendor="Arrae",
        )

    monkeypatch.setattr(chat_service, "ingest_product", fake_ingest)
    monkeypatch.setattr(response_composer.llm_client, "is_configured", lambda: False)
    async with await _client() as c:
        response = await c.post("/api/chat", json={"message": arrae_url})

    data = response.json()
    assert data["answer"]["intent"] == "product_summary"
    assert "**Magnesium** by Arrae" in data["answer"]["text"]


async def test_displayed_followups_do_not_reappear(source_url):
    async with await _client() as c:
        first = await c.post(
            "/api/chat",
            json={"message": f"{source_url}\nSummarize this product"},
        )
        first_data = first.json()
        selected = first_data["suggested_actions"][0]
        second = await c.post(
            "/api/chat",
            json={"session_id": first_data["session_id"], "message": selected},
        )

    second_actions = second.json()["suggested_actions"]
    assert set(first_data["suggested_actions"]).isdisjoint(second_actions)


async def test_saved_browser_suggestions_survive_backend_session_recovery(source_url):
    shown = [
        "What warnings are listed for Recharge Electrolytes?",
        "Are any allergens listed for Recharge Electrolytes?",
    ]
    async with await _client() as c:
        response = await c.post(
            "/api/chat",
            json={
                "session_id": "reopened-thread-with-suggestions",
                "product_url": source_url,
                "message": "Summarize this product",
                "shown_suggestions": shown,
            },
        )

    actions = response.json()["suggested_actions"]
    assert set(shown).isdisjoint(actions)


async def test_invalid_url_error():
    async with await _client() as c:
        r = await c.post("/api/chat", json={"message": "check https://evil.com/products/x please"})
    assert r.status_code == 400
    assert r.json()["code"] == "UNSUPPORTED_HOST"


async def test_evaluation_with_mocked_llm(monkeypatch, source_url):
    monkeypatch.setattr("app.intelligence.llm_client.is_configured", lambda: True)

    async def fake_json(system, user, **kw):
        return {
            "summary": "Solid page; images are the weak point.",
            "recommendations": [
                {"priority": 1, "title": "Add alt text", "rationale": "coverage low",
                 "suggested_action": "Write descriptive alt text", "evidence_fields": ["images"]},
            ],
            "limitations": ["Heuristic."],
        }

    monkeypatch.setattr("app.intelligence.llm_client.complete_json", fake_json)
    async with await _client() as c:
        r = await c.post("/api/chat", json={"message": f"{source_url}\nWhat can I improve on this page?"})
    d = r.json()
    assert d["evaluation"] is not None
    assert d["evaluation"]["overall_score"] > 0
    assert d["evaluation"]["recommendations"][0]["title"] == "Add alt text"
    assert d["answer"]["intent"] == "page_evaluation"


async def test_ambiguous_followup_receives_user_and_assistant_history(monkeypatch, source_url):
    captured = {}
    monkeypatch.setattr("app.intelligence.llm_client.is_configured", lambda: True)

    async def fake_json(system, user, **kw):
        captured.update(json.loads(user))
        return {"answer": "The strong rating matters because it is direct customer evidence."}

    monkeypatch.setattr("app.intelligence.llm_client.complete_json", fake_json)
    async with await _client() as c:
        first = await c.post(
            "/api/chat",
            json={"message": f"{source_url}\nDoes this product have reviews?"},
        )
        second = await c.post(
            "/api/chat",
            json={"session_id": first.json()["session_id"], "message": "Why does that matter?"},
        )

    history = captured["recent_conversation"]
    assert [turn["role"] for turn in history] == ["user", "assistant"]
    assert "Does this product have reviews?" in history[0]["text"]
    assert "516 reviews" in history[1]["text"]
    assert second.json()["answer"]["intent"] == "conversational_product_question"
    assert "customer evidence" in second.json()["answer"]["text"]


async def test_compound_question_keeps_all_grounded_tool_results(monkeypatch, source_url):
    captured = {}
    monkeypatch.setattr("app.intelligence.llm_client.is_configured", lambda: True)

    async def fake_json(system, user, **kw):
        captured.update(json.loads(user))
        return {
            "answer": "It contains magnesium and is currently in stock."
        }

    monkeypatch.setattr("app.intelligence.llm_client.complete_json", fake_json)
    async with await _client() as c:
        response = await c.post(
            "/api/chat",
            json={"message": f"{source_url}\nDoes it contain magnesium and is it in stock?"},
        )

    tool_intents = {result["intent"] for result in captured["grounded_tool_results"]}
    assert tool_intents == {"ingredient_lookup", "availability_lookup"}
    assert response.json()["answer"]["intent"] == "conversational_product_question"
    assert "magnesium" in response.json()["answer"]["text"]
    assert "in stock" in response.json()["answer"]["text"]


async def test_price_review_persuasion_uses_grounded_judgment(monkeypatch, source_url):
    monkeypatch.setattr("app.intelligence.llm_client.is_configured", lambda: True)

    async def should_not_call_llm(system, user, **kw):
        raise AssertionError("review persuasion should use the grounded response")

    monkeypatch.setattr("app.intelligence.llm_client.complete_json", should_not_call_llm)
    async with await _client() as c:
        response = await c.post(
            "/api/chat",
            json={
                "message": (
                    f"{source_url}\nCompare the price and reviews, and tell me which is more persuasive."
                )
            },
        )

    answer = response.json()["answer"]
    assert answer["intent"] == "conversational_product_question"
    assert "£18.99" in answer["text"]
    assert "516 reviews" in answer["text"]
    assert "social-proof signal" in answer["text"]
    assert "do **not** prove product quality" in answer["text"]


async def test_client_history_rehydrates_a_saved_thread(monkeypatch, source_url):
    captured = {}
    monkeypatch.setattr("app.intelligence.llm_client.is_configured", lambda: True)

    async def fake_json(system, user, **kw):
        captured.update(json.loads(user))
        return {"answer": "It refers to the subscription saving we discussed."}

    monkeypatch.setattr("app.intelligence.llm_client.complete_json", fake_json)
    browser_history = [
        {"role": "user", "text": "How much is the subscription?"},
        {"role": "assistant", "text": "The subscription price is £17.09."},
    ]
    async with await _client() as c:
        response = await c.post(
            "/api/chat",
            json={
                "session_id": "reopened-browser-thread",
                "product_url": source_url,
                "message": "Why is that useful?",
                "history": browser_history,
            },
        )

    assert captured["recent_conversation"] == browser_history
    assert response.status_code == 200
    assert "subscription saving" in response.json()["answer"]["text"]


async def test_streaming_emits_events(source_url):
    async with await _client() as c:
        async with c.stream("POST", "/api/chat/stream", json={"message": f"{source_url}\nDoes it have reviews?"}) as r:
            body = ""
            async for chunk in r.aiter_text():
                body += chunk
    assert "event: status" in body
    assert "event: product" in body
    assert "event: token" in body
    assert "event: complete" in body
