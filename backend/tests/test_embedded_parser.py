from app.ingestion import embedded_json_parser as ep


def test_finds_product_object(lmnt_html):
    obj = ep.find_product_object(lmnt_html)
    assert obj is not None
    assert obj["handle"] == "lmnt-recharge-electrolytes-variety-pack"


def test_parses_core_fields(lmnt_html, source_url):
    f = ep.parse(lmnt_html, source_url).fields
    assert f["title"].startswith("Recharge Electrolytes")
    assert f["vendor"] == "LMNT"
    assert f["product_type"] == "Vitamins & Supplements"
    assert f["available"] is True
    assert f["one_time_price"].amount == 18.99
    assert f["one_time_price"].currency == "GBP"


def test_parses_variants_and_images(lmnt_html, source_url):
    f = ep.parse(lmnt_html, source_url).fields
    assert len(f["variants"]) >= 1
    assert f["variants"][0].title == "12 sachets"
    assert len(f["images"]) >= 1
    assert any(i.is_primary for i in f["images"])


def test_parses_subscription(lmnt_html, source_url):
    f = ep.parse(lmnt_html, source_url).fields
    assert f["subscription_savings_percent"] == 10.0
    assert f["subscription_price"].amount < f["one_time_price"].amount
    assert len(f["selling_plans"]) >= 1


def test_empty_html_returns_empty_fragment(source_url):
    frag = ep.parse("<html><body>nothing</body></html>", source_url)
    assert frag.fields == {}
