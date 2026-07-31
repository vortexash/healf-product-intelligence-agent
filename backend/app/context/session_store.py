"""In-memory session + product cache with TTL (PRD 22, 25)."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from ..config import get_settings
from ..models import ProductData


@dataclass
class Session:
    id: str
    active_product_url: str | None = None
    product: ProductData | None = None
    messages: list[dict] = field(default_factory=list)
    suggested_actions_shown: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def _expired(self, s: Session) -> bool:
        return (time.time() - s.updated_at) > get_settings().session_ttl_seconds

    def get_or_create(self, session_id: str | None) -> Session:
        if session_id and session_id in self._sessions:
            s = self._sessions[session_id]
            if not self._expired(s):
                return s
            del self._sessions[session_id]
        sid = session_id or uuid.uuid4().hex
        s = Session(id=sid)
        self._sessions[sid] = s
        return s

    def touch(self, s: Session) -> None:
        s.updated_at = time.time()


class ProductCache:
    """10-minute in-memory cache keyed by normalized product URL."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, ProductData]] = {}

    def get(self, key: str) -> ProductData | None:
        hit = self._store.get(key)
        if not hit:
            return None
        ts, product = hit
        if (time.time() - ts) > get_settings().product_cache_ttl_seconds:
            del self._store[key]
            return None
        return product

    def set(self, key: str, product: ProductData) -> None:
        self._store[key] = (time.time(), product)


sessions = SessionStore()
product_cache = ProductCache()
