"""Probe classic Shopify public endpoints (PRD 14.2).

Healf is headless (these 404), but real Shopify themes expose /products/{h}.js
and .json. We probe locale-first, parse the standard shape when present, and
degrade gracefully to an empty fragment otherwise.
"""
from __future__ import annotations

from ..models import Money, ProductImage, ProductVariant
from ..navigation import ParsedProductUrl, try_fetch_json
from ..utilities import make_money
from .base import Fragment


def _candidate_urls(parsed: ParsedProductUrl) -> list[str]:
    loc = f"/{parsed.locale}" if parsed.locale else ""
    h = parsed.handle
    urls = [f"https://healf.com{loc}/products/{h}.js", f"https://healf.com{loc}/products/{h}.json"]
    if loc:
        urls += [f"https://healf.com/products/{h}.js", f"https://healf.com/products/{h}.json"]
    return urls


async def parse(parsed: ParsedProductUrl) -> Fragment:
    frag = Fragment(source_type="shopify_json")
    data = None
    src = ""
    for url in _candidate_urls(parsed):
        got = await try_fetch_json(url)
        if isinstance(got, dict) and (got.get("product") or got.get("variants") or got.get("title")):
            data = got.get("product", got)
            src = url
            break
    if not data:
        return frag

    frag.set("title", data.get("title"), src, confidence=0.95)
    frag.set("vendor", data.get("vendor"), src, confidence=0.95)
    frag.set("product_type", data.get("type") or data.get("product_type"), src, confidence=0.9)
    if data.get("description"):
        frag.set("description_html", data["description"], src, confidence=0.7)

    variants = []
    for v in data.get("variants") or []:
        price = make_money(float(v["price"]) / 100 if isinstance(v.get("price"), int) else v.get("price"))
        variants.append(
            ProductVariant(
                id=str(v.get("id")),
                title=v.get("title"),
                sku=v.get("sku"),
                available=v.get("available"),
                price=price,
            )
        )
    if variants:
        frag.set("variants", variants, src, confidence=0.95)
        if variants[0].price:
            frag.set("one_time_price", variants[0].price, src, confidence=0.95)
        frag.set("available", any(v.available for v in variants), src, confidence=0.9)

    images = []
    for i, im in enumerate(data.get("images") or []):
        url = im if isinstance(im, str) else im.get("src")
        if url:
            images.append(ProductImage(url=url, position=i + 1, is_primary=i == 0))
    if images:
        frag.set("images", images, src, confidence=0.9)
    return frag
