"""Dev-only: run parsers against the saved fixture and print merged product."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion import embedded_json_parser, html_parser, jsonld_parser, images_parser, reviews_parser, merger  # noqa: E402

html = (Path(__file__).resolve().parents[1] / "tests/fixtures/lmnt_recharge.html").read_text(encoding="utf-8")
src = "https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack"

frags = [
    embedded_json_parser.parse(html, src, None),
    jsonld_parser.parse(html, src),
    html_parser.parse(html, src),
    images_parser.parse(html, src),
    reviews_parser.parse(html, src),
]
p = merger.merge(
    source_url=src, handle="lmnt-recharge-electrolytes-variety-pack",
    locale="en-uk", selected_variant_id=None, fragments=frags,
)
print("title:", p.title)
print("vendor:", p.vendor, "| type:", p.product_type)
print("one_time:", p.one_time_price and p.one_time_price.formatted)
print("subscription:", p.subscription_price and p.subscription_price.formatted, "| savings%:", p.subscription_savings_percent)
print("available:", p.available)
print("variants:", [(v.title, v.price and v.price.formatted) for v in p.variants])
print("selling_plans:", [(sp.name, sp.discount_percent) for sp in p.selling_plans])
print("reviews:", p.reviews.model_dump())
print("images:", len(p.images), "| primary:", sum(i.is_primary for i in p.images), "| alt:", sum(bool(i.alt_text) for i in p.images))
print("benefits:", p.benefits[:3])
print("ingredients_raw:", (p.ingredients_raw or "")[:100])
print("ingredient_groups:", list(p.ingredient_groups.keys()))
print("suggested_use:", (p.suggested_use or "")[:80])
print("description_text words:", len((p.description_text or "").split()))
print("seo.title:", p.seo.title)
print("seo.desc:", (p.seo.description or "")[:80])
print("canonical:", p.canonical_url)
print("evidence fields:", sorted({e.field for e in p.evidence}))
print("warnings:", p.extraction_warnings)
