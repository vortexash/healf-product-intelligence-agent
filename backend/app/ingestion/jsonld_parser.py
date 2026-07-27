"""JSON-LD Product extraction (PRD 14.3)."""
from __future__ import annotations

import json
import re

from ..models import ReviewSummary
from ..utilities import excerpt, make_money
from .base import Fragment

_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
    re.IGNORECASE,
)


def _iter_nodes(data):
    """Yield every dict node from an object / list / @graph structure."""
    stack = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, dict):
            yield node
            if "@graph" in node and isinstance(node["@graph"], list):
                stack.extend(node["@graph"])


def _is_product(node: dict) -> bool:
    t = node.get("@type")
    if isinstance(t, list):
        return "Product" in t
    return t == "Product"


def parse(html: str, source_url: str) -> Fragment:
    frag = Fragment(source_type="json_ld")
    product = None
    for m in _LD_RE.finditer(html):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            frag.warnings.append("Skipped an invalid JSON-LD block.")
            continue
        for node in _iter_nodes(data):
            if _is_product(node):
                product = node
                break
        if product:
            break
    if not product:
        return frag

    frag.set("title", product.get("name"), source_url, excerpt(product.get("name")), confidence=0.85)
    brand = product.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")
    frag.set("vendor", brand, source_url, confidence=0.85)
    desc = product.get("description")
    if desc:
        frag.set("description_text", desc, source_url, excerpt(desc), confidence=0.6)

    offers = product.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else None
    if isinstance(offers, dict):
        currency = offers.get("priceCurrency", "GBP")
        money = make_money(offers.get("price"), currency)
        if money:
            frag.set("one_time_price", money, source_url, f"{money.formatted}", confidence=0.7)
        avail = (offers.get("availability") or "").lower()
        if avail:
            frag.set("available", "instock" in avail or "presale" in avail, source_url, avail, confidence=0.7)

    agg = product.get("aggregateRating")
    review_list = product.get("review")
    if isinstance(agg, dict) or review_list:
        rs = ReviewSummary(
            present=True,
            provider="healf_pdp",
            full_review_text_ingested=False,
        )
        if isinstance(agg, dict):
            try:
                rs.average_rating = float(agg.get("ratingValue"))
            except (ValueError, TypeError):
                pass
            try:
                rs.count = int(agg.get("reviewCount") or agg.get("ratingCount"))
            except (ValueError, TypeError):
                pass
        frag.set(
            "reviews",
            rs,
            source_url,
            f"rating={rs.average_rating} count={rs.count}",
            selector="script[type=application/ld+json] Product.aggregateRating",
            confidence=0.9,
        )
    return frag
