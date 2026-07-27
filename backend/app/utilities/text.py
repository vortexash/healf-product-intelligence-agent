"""Text normalization helpers."""
from __future__ import annotations

import re
import unicodedata

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# Dash family (em, en, figure, horizontal bar) -> plain hyphen. Keeps the UI free of "—".
_DASH_RE = re.compile(r"[‒–—―]")


def strip_dashes(obj):
    """Recursively replace em/en dashes with '-' in any str inside a dict/list/str.

    Applied at the API boundary so no long dash reaches the UI, whether the text
    came from a template, product data, or the LLM.
    """
    if isinstance(obj, str):
        return _DASH_RE.sub("-", obj)
    if isinstance(obj, dict):
        return {k: strip_dashes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [strip_dashes(v) for v in obj]
    return obj


def strip_html(html: str | None) -> str:
    if not html:
        return ""
    text = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html, flags=re.I)
    text = _TAG_RE.sub(" ", text)
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&nbsp;", " ")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
    )
    return _WS_RE.sub(" ", text).strip()


def normalize(text: str | None) -> str:
    """Lowercase, strip accents/punctuation, collapse whitespace — for matching."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("-", " ")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return _WS_RE.sub(" ", text).strip()


def word_count(text: str | None) -> int:
    return len(_WS_RE.split(text.strip())) if text and text.strip() else 0


def excerpt(text: str | None, limit: int = 240) -> str:
    t = strip_html(text) if text and "<" in text else (text or "")
    t = _WS_RE.sub(" ", t).strip()
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"
