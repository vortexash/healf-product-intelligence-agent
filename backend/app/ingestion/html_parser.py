"""Heading-aware HTML section extraction (PRD 14.5).

Healf renders product copy inside Radix UI accordions:
    <button aria-controls="X">Ingredients</button> ... <div id="X" role="region">...</div>
plus an inline "Key Benefits" markdown block. We map section titles (via an
alias table) to normalized product fields and never scrape nav/footer/cookie text.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..utilities import excerpt, strip_html
from .base import Fragment

# Section title (normalized) -> field
ALIASES = {
    "product description": "description",
    "description": "description",
    "why this brand is healf": "brand_story",
    "key benefits": "benefits",
    "benefits": "benefits",
    "ingredients": "ingredients",
    "nutritional information": "ingredients",
    "nutrition": "ingredients",
    "suggested use": "suggested_use",
    "directions": "suggested_use",
    "how to use": "suggested_use",
    "warnings": "warnings",
    "important information": "warnings",
}
# "why <brand> is healf" -> brand_story
_WHY_RE = re.compile(r"^why .+ is healf$")


def _norm_title(t: str) -> str:
    t = re.sub(r"\s+", " ", (t or "").strip().lower())
    return t


def _classify(title: str) -> str | None:
    n = _norm_title(title)
    if n in ALIASES:
        return ALIASES[n]
    if _WHY_RE.match(n):
        return "brand_story"
    return None


def _bullets(node) -> list[str]:
    items = [strip_html(str(li)) for li in node.find_all("li")]
    return [i for i in items if i]


def _ingredient_groups(raw: str) -> dict[str, list[str]]:
    """Split 'Citrus: a, b, c\nOrange: d, e' into {group: [ingredients]}."""
    groups: dict[str, list[str]] = {}
    for line in re.split(r"[\n\r]+|(?<=[a-z0-9)])\.\s+(?=[A-Z][a-z]+:)", raw):
        line = line.strip()
        m = re.match(r"^([A-Z][A-Za-z /&]{2,30}):\s*(.+)$", line)
        if m:
            name = m.group(1).strip()
            items = [x.strip(" .") for x in re.split(r",|;", m.group(2)) if x.strip(" .")]
            if items:
                groups[name] = items
    return groups


def _collect_sections(soup: BeautifulSoup) -> list[tuple[str, object]]:
    """Return (title, content_node) pairs from accordions + inline markdown blocks."""
    out: list[tuple[str, object]] = []
    # Radix accordions: button[aria-controls] -> region div[id]
    for btn in soup.select("button[aria-controls]"):
        title = btn.get_text(" ", strip=True)
        region = soup.find(id=btn.get("aria-controls"))
        if title and region:
            out.append((title, region))
    # Inline markdown blocks whose first <strong> is a heading (e.g. Key Benefits)
    for block in soup.select("[class*=markdown]"):
        strong = block.find("strong")
        if strong:
            out.append((strong.get_text(" ", strip=True), block))
    return out


def parse(html: str, source_url: str) -> Fragment:
    frag = Fragment(source_type="html")
    soup = BeautifulSoup(html, "lxml")

    # --- Meta / SEO ---
    def meta(name=None, prop=None):
        tag = soup.find("meta", attrs={"name": name} if name else {"property": prop})
        return tag.get("content") if tag and tag.get("content") else None

    canonical = soup.find("link", rel="canonical")
    seo_title = meta(prop="og:title") or (soup.title.string if soup.title else None)
    seo_desc = meta(name="description") or meta(prop="og:description")
    from ..models import SeoData

    if seo_title or seo_desc or canonical:
        frag.set(
            "seo",
            SeoData(
                title=seo_title,
                description=seo_desc,
                canonical_url=canonical.get("href") if canonical else None,
            ),
            source_url,
            excerpt(seo_title),
            selector="meta",
            confidence=0.85,
        )
    if canonical and canonical.get("href"):
        frag.set("canonical_url", canonical["href"], source_url, confidence=0.9)

    # --- Sections ---
    description_parts: list[str] = []
    seen_titles: set[str] = set()
    for title, node in _collect_sections(soup):
        field = _classify(title)
        if not field:
            continue
        key = f"{field}:{_norm_title(title)}"
        if key in seen_titles:
            continue
        seen_titles.add(key)
        text = strip_html(str(node))
        if not text or len(text) < 3:
            continue
        sel = f"section:{_norm_title(title)}"

        if field == "benefits":
            bullets = _bullets(node) or [text]
            # Drop the leading "Key Benefits" label if captured as a bullet.
            bullets = [b for b in bullets if _norm_title(b) not in ALIASES]
            frag.set("benefits", bullets, source_url, excerpt(text), sel, confidence=0.8)
        elif field == "ingredients":
            frag.set("ingredients_raw", text, source_url, excerpt(text), sel, confidence=0.85)
            groups = _ingredient_groups(text)
            if groups:
                frag.set("ingredient_groups", groups, source_url, excerpt(text), sel, confidence=0.8)
        elif field == "suggested_use":
            frag.set("suggested_use", text, source_url, excerpt(text), sel, confidence=0.85)
        elif field == "warnings":
            frag.set("warnings", [text], source_url, excerpt(text), sel, confidence=0.8)
        elif field in ("description", "brand_story"):
            description_parts.append(text)

    if description_parts:
        joined = "\n\n".join(description_parts)
        frag.set("description_text", joined, source_url, excerpt(joined), "section:description", confidence=0.8)
        frag.set("description_html", joined, source_url, confidence=0.5)

    return frag
