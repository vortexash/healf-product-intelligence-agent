"""Extract Healf's embedded Shopify Storefront product object.

Healf is a headless Next.js storefront. The rich structured product data ships
inside React Server Component flight payloads: `self.__next_f.push([1,"..."])`.
We decode those string literals, concatenate the stream, locate the
`"product":{...}` object, and map the Shopify Storefront GraphQL shape.
(PRD 14.4 — embedded storefront JSON.)
"""
from __future__ import annotations

import json
import re

from ..models import Money, ProductImage, ProductVariant, SellingPlan, SeoData
from ..utilities import excerpt, make_money
from .base import Fragment

_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[\d+,\s*(".*?")\]\)', re.DOTALL)


def decode_flight_stream(html: str) -> str:
    """Decode and concatenate all __next_f flight string literals."""
    parts = []
    for m in _PUSH_RE.finditer(html):
        try:
            parts.append(json.loads(m.group(1)))
        except (ValueError, TypeError):
            continue
    return "".join(parts)


def _extract_object(s: str, brace_start: int) -> str | None:
    """Return the balanced {...} JSON object beginning at brace_start."""
    depth = 0
    instr = False
    esc = False
    for i in range(brace_start, len(s)):
        c = s[i]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return s[brace_start : i + 1]
    return None


def find_product_object(html: str) -> dict | None:
    stream = decode_flight_stream(html)
    key = '"product":{'
    idx = stream.find(key)
    while idx != -1:
        brace = idx + len(key) - 1
        raw = _extract_object(stream, brace)
        if raw:
            try:
                obj = json.loads(raw)
            except (ValueError, TypeError):
                obj = None
            if obj and ("variants" in obj or "priceRange" in obj or "handle" in obj):
                return obj
        idx = stream.find(key, idx + 1)
    return None


def _edges(node) -> list:
    if isinstance(node, dict) and isinstance(node.get("edges"), list):
        return [e.get("node", e) for e in node["edges"]]
    if isinstance(node, list):
        return node
    return []


def _money(node) -> Money | None:
    if isinstance(node, dict):
        return make_money(node.get("amount"), node.get("currencyCode", "GBP"))
    return None


def _subscription(product: dict, one_time: Money | None) -> tuple[list[SellingPlan], Money | None, float | None]:
    plans: list[SellingPlan] = []
    best_pct: float | None = None
    for group in _edges(product.get("sellingPlanGroups")):
        for sp in _edges(group.get("sellingPlans") if isinstance(group, dict) else None):
            if not isinstance(sp, dict):
                continue
            pct = None
            for adj in sp.get("priceAdjustments") or []:
                val = (adj or {}).get("adjustmentValue") or {}
                # Percentage or fixed-amount discounts appear under varying keys.
                for k in ("adjustmentPercentage", "percentage", "value"):
                    if isinstance(val.get(k), (int, float)):
                        pct = float(val[k])
                        break
                if pct is not None:
                    break
            plans.append(
                SellingPlan(
                    id=str(sp.get("id")) if sp.get("id") else None,
                    name=sp.get("name"),
                    description=sp.get("description"),
                    discount_percent=pct,
                )
            )
            if pct is not None and (best_pct is None or pct > best_pct):
                best_pct = pct
    sub_price = None
    if one_time and best_pct:
        sub_price = make_money(round(one_time.amount * (1 - best_pct / 100), 2), one_time.currency)
    return plans, sub_price, best_pct


def parse(html: str, source_url: str, url_variant_id: str | None = None) -> Fragment:
    frag = Fragment(source_type="embedded_json")
    product = find_product_object(html)
    if not product:
        return frag

    frag.set("title", product.get("title"), source_url, confidence=0.9)
    frag.set("vendor", product.get("vendor"), source_url, confidence=0.9)
    frag.set("product_type", product.get("productType"), source_url, confidence=0.9)
    if isinstance(product.get("availableForSale"), bool):
        frag.set("available", product["availableForSale"], source_url, confidence=0.9)

    seo = product.get("seo") or {}
    if seo.get("title") or seo.get("description"):
        frag.set(
            "seo",
            SeoData(title=seo.get("title"), description=seo.get("description")),
            source_url,
            excerpt(seo.get("title")),
            confidence=0.9,
        )

    # Prices from priceRange (min variant) as the one-time price.
    pr = product.get("priceRange") or {}
    one_time = _money(pr.get("minVariantPrice"))
    if one_time:
        frag.set("one_time_price", one_time, source_url, one_time.formatted, confidence=0.95)

    # Variants
    variants: list[ProductVariant] = []
    selected_id = None
    for v in _edges(product.get("variants")):
        if not isinstance(v, dict):
            continue
        opts = {o.get("name"): o.get("value") for o in v.get("selectedOptions") or [] if isinstance(o, dict)}
        variants.append(
            ProductVariant(
                id=str(v.get("id")) if v.get("id") else None,
                title=v.get("title"),
                available=v.get("availableForSale"),
                price=_money(v.get("price")),
                compare_at_price=_money(v.get("compareAtPrice")),
                options=opts,
            )
        )
    if variants:
        frag.set("variants", variants, source_url, f"{len(variants)} variant(s)", confidence=0.9)

    sel = product.get("selectedOrFirstAvailableVariant") or {}
    selected_id = str(sel.get("id")) if sel.get("id") else None
    # URL-specified variant wins (PRD 15.1 exception).
    if url_variant_id:
        for v in variants:
            if v.id and url_variant_id in v.id:
                selected_id = v.id
                if v.compare_at_price:
                    frag.set("compare_at_price", v.compare_at_price, source_url, confidence=0.9)
                if v.price:
                    frag.set("one_time_price", v.price, source_url, v.price.formatted, confidence=0.96)
    if selected_id:
        frag.set("selected_variant_id", selected_id, source_url, confidence=0.9)
    if isinstance(sel.get("compareAtPrice"), dict):
        cap = _money(sel.get("compareAtPrice"))
        if cap:
            frag.set("compare_at_price", cap, source_url, confidence=0.9)

    # Subscription
    plans, sub_price, pct = _subscription(product, one_time)
    if plans:
        frag.set("selling_plans", plans, source_url, f"{len(plans)} plan(s)", confidence=0.85)
    if sub_price:
        frag.set("subscription_price", sub_price, source_url, sub_price.formatted, confidence=0.8)
    if pct:
        frag.set("subscription_savings_percent", pct, source_url, f"{pct}%", confidence=0.8)

    # Images
    images: list[ProductImage] = []
    seen = set()
    featured = product.get("featuredImage") or {}
    featured_src = featured.get("src") or featured.get("originalSrc")
    for node in _edges(product.get("images")):
        if not isinstance(node, dict):
            continue
        src = node.get("src") or node.get("originalSrc")
        if not src or src in seen:
            continue
        seen.add(src)
        images.append(
            ProductImage(
                url=src,
                alt_text=node.get("altText"),
                position=len(images) + 1,
                is_primary=(src == featured_src),
            )
        )
    if featured_src and featured_src not in seen:
        images.insert(0, ProductImage(url=featured_src, alt_text=featured.get("altText"), position=0, is_primary=True))
    if images:
        if not any(i.is_primary for i in images):
            images[0].is_primary = True
        frag.set("images", images, source_url, f"{len(images)} image(s)", confidence=0.9)

    return frag
