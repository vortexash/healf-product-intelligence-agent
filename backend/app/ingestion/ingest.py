"""Orchestrate live fetch + all parsers into a normalized product (PRD 14-15)."""
from __future__ import annotations

from ..models import AppError, ProductData
from ..navigation import ParsedProductUrl, fetch
from ..utilities.logging import get_logger
from . import (
    embedded_json_parser,
    html_parser,
    images_parser,
    jsonld_parser,
    merger,
    reviews_parser,
    shopify_parser,
)
from .base import Fragment

log = get_logger("ingest")


async def ingest_product(parsed: ParsedProductUrl) -> ProductData:
    """Fetch the live page and merge every parser's output. Partial failures
    of individual parsers add warnings but never abort the whole request."""
    result = await fetch(parsed.fetch_urls[0])
    html = result.text
    src = result.url

    fragments: list[Fragment] = []

    # Shopify endpoint probe (async; 404 on Healf -> empty).
    try:
        fragments.append(await shopify_parser.parse(parsed))
    except AppError:
        raise
    except Exception as e:  # noqa: BLE001 - one parser must not fail the request
        fragments.append(_warn_fragment("shopify_json", f"Shopify probe failed: {e}"))

    for name, fn in [
        ("embedded_json", lambda: embedded_json_parser.parse(html, src, parsed.variant_id)),
        ("json_ld", lambda: jsonld_parser.parse(html, src)),
        ("html", lambda: html_parser.parse(html, src)),
        ("images", lambda: images_parser.parse(html, src)),
        ("reviews", lambda: reviews_parser.parse(html, src)),
    ]:
        try:
            fragments.append(fn())
        except Exception as e:  # noqa: BLE001
            log.warning("parser %s failed: %s", name, e)
            fragments.append(_warn_fragment("derived", f"{name} parser could not run."))

    product = merger.merge(
        source_url=parsed.normalized_url,
        handle=parsed.handle,
        locale=parsed.locale,
        selected_variant_id=parsed.variant_id,
        fragments=fragments,
    )

    if not product.title and not product.images and product.reviews.count is None:
        raise AppError("PRODUCT_PARSE_FAILED", "I loaded the page but could not extract product data.", 422)

    _add_partial_warnings(product)
    return product


def _warn_fragment(source, msg) -> Fragment:
    f = Fragment(source_type=source)
    f.warnings.append(msg)
    return f


def _add_partial_warnings(p: ProductData) -> None:
    if p.reviews.count is None and p.reviews.present is None:
        p.extraction_warnings.append("Review details could not be retrieved from this page.")
    if not p.ingredients_raw:
        p.extraction_warnings.append("No ingredients section was found on this page.")
