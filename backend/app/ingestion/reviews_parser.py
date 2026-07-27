"""Review summary fallback (PRD 14.6).

Primary review data comes from the JSON-LD aggregateRating. This fallback scans
visible page text / widget attributes for a review count + rating when JSON-LD
is absent. It never claims full review-text ingestion.
"""
from __future__ import annotations

import re

from ..models import ReviewSummary
from .base import Fragment

_COUNT_RE = re.compile(r"([\d,]{1,7})\s*(?:reviews?|ratings?)", re.IGNORECASE)
_RATING_RE = re.compile(r"([0-4](?:\.\d)?|5(?:\.0)?)\s*(?:out of\s*5|/\s*5|stars?)", re.IGNORECASE)


def parse(text_or_html: str, source_url: str) -> Fragment:
    frag = Fragment(source_type="review_widget")
    # Work on visible-ish text (strip tags cheaply).
    text = re.sub(r"<[^>]+>", " ", text_or_html)
    count = None
    cm = _COUNT_RE.search(text)
    if cm:
        try:
            count = int(cm.group(1).replace(",", ""))
        except ValueError:
            count = None
    rating = None
    rm = _RATING_RE.search(text)
    if rm:
        try:
            rating = float(rm.group(1))
        except ValueError:
            rating = None
    if count or rating:
        frag.set(
            "reviews",
            ReviewSummary(
                present=True,
                count=count,
                average_rating=rating,
                provider="page_text",
                full_review_text_ingested=False,
            ),
            source_url,
            (cm.group(0) if cm else rm.group(0)),
            confidence=0.5,
        )
    return frag
