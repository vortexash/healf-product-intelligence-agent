from app.ingestion import html_parser as hp


def test_extracts_sections(lmnt_html, source_url):
    f = hp.parse(lmnt_html, source_url).fields
    assert "ingredients_raw" in f
    assert "suggested_use" in f
    assert f["benefits"]
    assert f["description_text"]


def test_ingredient_groups_by_flavour(lmnt_html, source_url):
    f = hp.parse(lmnt_html, source_url).fields
    groups = f["ingredient_groups"]
    assert "Citrus" in groups
    assert len(groups) >= 2  # multiple flavours separated


def test_meta_and_canonical(lmnt_html, source_url):
    f = hp.parse(lmnt_html, source_url).fields
    assert f["seo"].title
    assert f["canonical_url"].startswith("https://healf.com")


def test_synthetic_accordion():
    html = """
    <button aria-controls="s1">Ingredients</button>
    <div id="s1" role="region"><p>Water, Sugar, Salt.</p></div>
    <button aria-controls="s2">Suggested Use</button>
    <div id="s2" role="region"><p>Take one daily.</p></div>
    """
    f = hp.parse(html, "https://healf.com/products/x").fields
    assert "Water" in f["ingredients_raw"]
    assert "one daily" in f["suggested_use"]
