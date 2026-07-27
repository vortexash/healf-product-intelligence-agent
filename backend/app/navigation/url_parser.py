"""Extract and normalize Healf product URLs from free text (PRD 13.1)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from ..models import AppError

ALLOWED_HOSTS = {"healf.com", "www.healf.com"}
MAX_URL_LEN = 2048
ALLOWED_PORTS = {None, 443}
# Matches a bare or full URL; we validate strictly afterwards.
URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)
# locale like en-uk, en-us, fr-fr
LOCALE_RE = re.compile(r"^[a-z]{2}-[a-z]{2}$", re.IGNORECASE)


@dataclass
class ParsedProductUrl:
    normalized_url: str  # canonical https://healf.com/{locale}/products/{handle}?variant=...
    handle: str
    locale: str | None
    variant_id: str | None
    selling_plan_id: str | None
    fetch_urls: list[str]  # candidate live URLs to try (locale-first)


def extract_url(text: str) -> str | None:
    """Return the first URL-looking token in text, if any."""
    m = URL_RE.search(text or "")
    return m.group(0).rstrip(".,);") if m else None


def parse_and_validate(raw: str) -> ParsedProductUrl:
    """Strictly validate a Healf product URL and return normalized parts.

    Raises AppError with codes INVALID_URL / UNSUPPORTED_HOST / NOT_A_PRODUCT_URL.
    """
    if not raw or len(raw) > MAX_URL_LEN:
        raise AppError("INVALID_URL", "Please provide a public Healf product URL containing /products/.")

    raw = raw.strip()
    try:
        u = urlparse(raw)
    except ValueError:
        raise AppError("INVALID_URL", "That URL could not be parsed.")

    if u.scheme.lower() != "https":
        raise AppError("INVALID_URL", "Only secure https Healf URLs are supported.")

    # Credentials embedded in the URL are rejected.
    if u.username or u.password or "@" in (u.netloc or ""):
        raise AppError("INVALID_URL", "URLs with embedded credentials are not allowed.")

    host = (u.hostname or "").lower()
    if u.port not in ALLOWED_PORTS:
        raise AppError("INVALID_URL", "Unexpected port in URL.")
    if host not in ALLOWED_HOSTS:
        raise AppError("UNSUPPORTED_HOST", "Only public healf.com product URLs are supported.")

    # Path: optional locale segment, then /products/{handle}
    parts = [p for p in u.path.split("/") if p]
    if "products" not in parts:
        raise AppError("NOT_A_PRODUCT_URL", "Please provide a URL containing /products/.")
    pidx = parts.index("products")
    if pidx + 1 >= len(parts):
        raise AppError("NOT_A_PRODUCT_URL", "The URL is missing a product handle.")
    handle = parts[pidx + 1]
    locale = parts[0] if pidx == 1 and LOCALE_RE.match(parts[0]) else None
    if pidx not in (0, 1):
        raise AppError("NOT_A_PRODUCT_URL", "Unexpected product path structure.")

    q = parse_qs(u.query)
    variant_id = (q.get("variant") or [None])[0]
    selling_plan_id = (q.get("selling_plan") or [None])[0]

    # Normalized display URL (host without www).
    query = ""
    if variant_id:
        query = f"?variant={variant_id}"
        if selling_plan_id:
            query += f"&selling_plan={selling_plan_id}"
    elif selling_plan_id:
        query = f"?selling_plan={selling_plan_id}"
    loc = f"/{locale}" if locale else ""
    normalized = f"https://healf.com{loc}/products/{handle}{query}"

    # Fetch candidates: locale page first (that is what actually renders data),
    # then bare product page as fallback.
    fetch_urls: list[str] = []
    base = f"https://healf.com{loc}/products/{handle}"
    fetch_urls.append(base + query)
    if loc:
        fetch_urls.append(f"https://healf.com/products/{handle}" + query)

    return ParsedProductUrl(
        normalized_url=normalized,
        handle=handle,
        locale=locale,
        variant_id=variant_id,
        selling_plan_id=selling_plan_id,
        fetch_urls=fetch_urls,
    )
