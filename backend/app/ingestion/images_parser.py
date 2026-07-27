"""Product image fallback from rendered HTML (PRD 14.7).

Primary images come from embedded flight JSON. This fallback harvests Shopify
CDN product images from <img>/srcset when flight data is unavailable, dropping
logos, icons, payment badges and tiny/tracking images, deduped by canonical URL.
"""
from __future__ import annotations

import re

from ..models import ProductImage
from .base import Fragment

_PRODUCT_IMG_RE = re.compile(
    r"https://cdn\.shopify\.com/s/files/[^\s\"'\\)]+\.(?:png|jpe?g|webp)[^\s\"'\\)]*",
    re.IGNORECASE,
)
_IGNORE = ("logo", "icon", "payment", "sprite", "placeholder", "favicon")


def _canonical(url: str) -> str:
    # Strip Shopify transform suffix (_400x, _1024x1024) and query to dedupe.
    url = re.sub(r"[?&](v|width|height)=[^&]*", "", url)
    url = re.sub(r"_(?:\d+x\d*|\d*x\d+)(?=\.[a-z]+)", "", url)
    return url.split("?")[0]


def parse(html: str, source_url: str) -> Fragment:
    frag = Fragment(source_type="html")
    seen: set[str] = set()
    images: list[ProductImage] = []
    for m in _PRODUCT_IMG_RE.finditer(html):
        raw = m.group(0)
        low = raw.lower()
        if any(bad in low for bad in _IGNORE):
            continue
        canon = _canonical(raw)
        if canon in seen:
            continue
        seen.add(canon)
        images.append(ProductImage(url=raw, position=len(images) + 1, is_primary=len(images) == 0))
    if images:
        frag.set("images", images, source_url, f"{len(images)} image(s) from HTML", "img[src]", confidence=0.6)
    return frag
