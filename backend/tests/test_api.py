import json

import pytest
from httpx import ASGITransport, AsyncClient

from app import chat_service
from app.intelligence import evaluator, response_composer
from app.main import app
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
        "Show me 3 reviews",
        "Show the latest review",
        "What is the average rating?",
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


async def test_no_active_product_error():
    async with await _client() as c:
        r = await c.post("/api/chat", json={"message": "What can I improve?"})
    assert r.status_code == 400
    assert r.json()["code"] == "NO_ACTIVE_PRODUCT"


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
