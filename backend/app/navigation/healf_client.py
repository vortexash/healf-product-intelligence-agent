"""SSRF-safe live Healf fetch client (PRD 13.3)."""
from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import get_settings
from ..models import AppError
from .validator import assert_safe_host

MAX_REDIRECTS = 3
MAX_BODY_BYTES = 4_000_000  # ~4MB response cap


class FetchResult:
    def __init__(self, url: str, status: int, text: str, content_type: str):
        self.url = url
        self.status = status
        self.text = text
        self.content_type = content_type


def _timeout() -> httpx.Timeout:
    s = get_settings()
    return httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=s.request_timeout_seconds)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),  # 1 try + 2 retries
    wait=wait_exponential(multiplier=0.4, max=3),
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
)
async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    return await client.get(url)


async def fetch(url: str) -> FetchResult:
    """Fetch a validated Healf URL, revalidating host on every redirect hop."""
    settings = get_settings()
    headers = {"User-Agent": settings.http_user_agent, "Accept": "text/html,application/json"}
    assert_safe_host(url)

    async with httpx.AsyncClient(
        follow_redirects=False, timeout=_timeout(), headers=headers
    ) as client:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            assert_safe_host(current)
            try:
                resp = await _get(client, current)
            except httpx.TimeoutException:
                raise AppError("PRODUCT_FETCH_TIMEOUT", "The product page took too long to respond.", 504)
            except httpx.TransportError:
                raise AppError("PRODUCT_FETCH_BLOCKED", "Could not reach the product page.", 502)

            if resp.is_redirect:
                loc = resp.headers.get("location")
                if not loc:
                    break
                current = str(httpx.URL(current).join(loc))
                continue

            body = resp.content[:MAX_BODY_BYTES]
            text = body.decode(resp.encoding or "utf-8", errors="replace")
            if resp.status_code == 404:
                raise AppError("PRODUCT_NOT_FOUND", "This product page could not be found.", 404)
            if resp.status_code >= 400:
                raise AppError("PRODUCT_FETCH_BLOCKED", "The product page blocked automated access.", 502)
            return FetchResult(
                url=str(resp.url),
                status=resp.status_code,
                text=text,
                content_type=resp.headers.get("content-type", ""),
            )
    raise AppError("PRODUCT_FETCH_BLOCKED", "Too many redirects while loading the product.", 502)


async def try_fetch_json(url: str) -> dict | list | None:
    """Best-effort GET that returns parsed JSON, or None on any failure/non-JSON.

    Used to probe Shopify .js/.json endpoints which may not exist (404 on Healf).
    """
    try:
        res = await fetch(url)
    except AppError:
        return None
    ct = res.content_type.lower()
    if "json" not in ct and "javascript" not in ct:
        return None
    import json

    try:
        return json.loads(res.text)
    except (ValueError, TypeError):
        return None
