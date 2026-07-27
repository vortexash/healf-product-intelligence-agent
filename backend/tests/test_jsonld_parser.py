from app.ingestion import jsonld_parser as jp

GRAPH_HTML = """
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
  {"@type":"BreadcrumbList"},
  {"@type":"Product","name":"Test Product","brand":{"@type":"Brand","name":"Acme"},
   "description":"A thing.","offers":{"@type":"Offer","price":"9.99","priceCurrency":"GBP","availability":"https://schema.org/InStock"},
   "aggregateRating":{"@type":"AggregateRating","ratingValue":"4.2","reviewCount":37}}
]}
</script>
"""


def test_lmnt_reviews_from_aggregate(lmnt_html, source_url):
    f = jp.parse(lmnt_html, source_url).fields
    assert f["reviews"].count == 516
    assert f["reviews"].average_rating == 4.9
    assert f["reviews"].present is True
    assert f["reviews"].full_review_text_ingested is False


def test_graph_structure_and_offers():
    f = jp.parse(GRAPH_HTML, "https://healf.com/products/x").fields
    assert f["title"] == "Test Product"
    assert f["vendor"] == "Acme"
    assert f["one_time_price"].amount == 9.99
    assert f["available"] is True
    assert f["reviews"].average_rating == 4.2
    assert f["reviews"].count == 37


def test_invalid_jsonld_is_skipped():
    html = '<script type="application/ld+json">{bad json</script>'
    frag = jp.parse(html, "https://healf.com/products/x")
    assert frag.fields == {}
    assert frag.warnings
