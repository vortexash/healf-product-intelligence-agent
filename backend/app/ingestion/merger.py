"""Merge parser fragments into a normalized ProductData (PRD 15)."""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import ProductData, ProductImage, ReviewSummary, SourceEvidence
from ..utilities import strip_html
from .base import Fragment
from .images_parser import _canonical

# Source precedence (higher wins). PRD 15.1 default order.
RANK = {
    "shopify_json": 6,
    "embedded_json": 5,
    "json_ld": 4,
    "html": 3,
    "review_widget": 2,
    "derived": 1,
}

# Per-field overrides where a lower-general-rank source is authoritative.
FIELD_PREF = {
    "seo": ["html", "embedded_json"],
    "canonical_url": ["html", "json_ld", "embedded_json"],
    "reviews": ["json_ld", "review_widget", "embedded_json"],
    "description_text": ["html", "json_ld", "embedded_json"],
    "ingredients_raw": ["html"],
    "benefits": ["html"],
    "suggested_use": ["html"],
    "warnings": ["html"],
}

SCALAR_CONFLICT_FIELDS = {"title", "vendor", "available", "one_time_price"}


def _pref_rank(field: str, source_type: str) -> int:
    if field in FIELD_PREF:
        order = FIELD_PREF[field]
        return (len(order) - order.index(source_type)) if source_type in order else 0
    return RANK.get(source_type, 0)


def merge(
    *,
    source_url: str,
    handle: str,
    locale: str | None,
    selected_variant_id: str | None,
    fragments: list[Fragment],
) -> ProductData:
    chosen: dict[str, tuple[object, str, int]] = {}  # field -> (value, source, rank)
    evidence: list[SourceEvidence] = []
    warnings: list[str] = []

    image_lists: list[list[ProductImage]] = []

    for frag in fragments:
        warnings.extend(frag.warnings)
        evidence.extend(frag.evidence)
        for field, value in frag.fields.items():
            if field == "images":
                image_lists.append(value)
                continue
            rank = _pref_rank(field, frag.source_type)
            if field not in chosen:
                chosen[field] = (value, frag.source_type, rank)
                continue
            cur_val, cur_src, cur_rank = chosen[field]
            if rank > cur_rank:
                if field in SCALAR_CONFLICT_FIELDS and _differs(cur_val, value):
                    warnings.append(
                        f"Conflicting {field}: '{_short(cur_val)}' ({cur_src}) vs "
                        f"'{_short(value)}' ({frag.source_type}); used {frag.source_type}."
                    )
                chosen[field] = (value, frag.source_type, rank)
            elif rank == cur_rank and field in SCALAR_CONFLICT_FIELDS and _differs(cur_val, value):
                warnings.append(f"Ambiguous {field} across sources; kept {cur_src} value.")

    fields = {k: v[0] for k, v in chosen.items()}

    merged_images = _union_images(image_lists)
    if merged_images:
        fields["images"] = merged_images

    # Reviews merge: prefer the entry with a count.
    reviews = fields.get("reviews") or ReviewSummary()
    fields["reviews"] = reviews

    # Derived description_text from html if only html present.
    if fields.get("description_html") and not fields.get("description_text"):
        fields["description_text"] = strip_html(fields["description_html"])

    # Lower confidence on evidence for fields flagged as conflicting.
    conflict_fields = {w.split()[1].rstrip(":") for w in warnings if w.startswith("Conflicting")}
    for ev in evidence:
        if ev.field in conflict_fields:
            ev.confidence = min(ev.confidence, 0.6)

    product = ProductData(
        source_url=source_url,
        handle=handle,
        locale=locale,
        retrieved_at=datetime.now(timezone.utc),
        selected_variant_id=fields.get("selected_variant_id") or selected_variant_id,
        evidence=_dedupe_evidence(evidence),
        extraction_warnings=_dedupe(warnings),
        **{k: v for k, v in fields.items() if k in ProductData.model_fields and k not in ("selected_variant_id",)},
    )
    return product


def _union_images(lists: list[list[ProductImage]]) -> list[ProductImage]:
    """Union images across sources, deduped by canonical URL. Richer sources
    (listed first) win on alt text / primary flag."""
    by_canon: dict[str, ProductImage] = {}
    for imgs in lists:
        for img in imgs:
            key = _canonical(img.url)
            existing = by_canon.get(key)
            if existing is None:
                by_canon[key] = img.model_copy()
            else:
                if not existing.alt_text and img.alt_text:
                    existing.alt_text = img.alt_text
                if img.is_primary:
                    existing.is_primary = True
    out = list(by_canon.values())
    if out and not any(i.is_primary for i in out):
        out[0].is_primary = True
    for i, img in enumerate(out):
        img.position = i + 1
    return out


def _differs(a, b) -> bool:
    try:
        return strip_html(str(a)).strip().lower() != strip_html(str(b)).strip().lower()
    except Exception:
        return a != b


def _short(v) -> str:
    s = str(v)
    return s if len(s) <= 40 else s[:39] + "…"


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _dedupe_evidence(items: list[SourceEvidence]) -> list[SourceEvidence]:
    seen, out = set(), []
    for ev in items:
        key = (ev.field, ev.source_type)
        if key not in seen:
            seen.add(key)
            out.append(ev)
    return out
