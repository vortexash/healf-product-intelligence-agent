from app.ingestion.base import Fragment
from app.ingestion.merger import merge
from app.models import Money, ProductImage


def _merge(fragments):
    return merge(
        source_url="https://healf.com/en-uk/products/x",
        handle="x",
        locale="en-uk",
        selected_variant_id=None,
        fragments=fragments,
    )


def test_source_precedence():
    low = Fragment("html")
    low.set("title", "HTML Title", "u")
    high = Fragment("embedded_json")
    high.set("title", "Embedded Title", "u")
    p = _merge([low, high])
    assert p.title == "Embedded Title"  # embedded outranks html


def test_conflict_adds_warning():
    a = Fragment("json_ld")
    a.set("title", "Alpha", "u")
    b = Fragment("embedded_json")
    b.set("title", "Beta", "u")
    p = _merge([a, b])
    assert any("Conflicting title" in w for w in p.extraction_warnings)


def test_images_unioned_and_deduped():
    a = Fragment("embedded_json")
    a.set("images", [ProductImage(url="https://cdn.shopify.com/s/files/a.png?v=1", is_primary=True)], "u")
    b = Fragment("html")
    b.set("images", [
        ProductImage(url="https://cdn.shopify.com/s/files/a.png?v=2"),  # dup of a
        ProductImage(url="https://cdn.shopify.com/s/files/b.png"),
    ], "u")
    p = _merge([a, b])
    assert len(p.images) == 2
    assert sum(i.is_primary for i in p.images) == 1


def test_evidence_retained():
    a = Fragment("json_ld")
    a.set("one_time_price", Money(amount=5.0), "u", excerpt="£5")
    p = _merge([a])
    assert any(e.field == "one_time_price" for e in p.evidence)


def test_seo_prefers_html_over_embedded():
    from app.models import SeoData

    emb = Fragment("embedded_json")
    emb.set("seo", SeoData(title="Embedded SEO"), "u")
    html = Fragment("html")
    html.set("seo", SeoData(title="HTML SEO"), "u")
    p = _merge([emb, html])
    assert p.seo.title == "HTML SEO"
