"""API request/response + content draft models (PRD 12.3)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .evaluation import ProductEvaluation
from .product import ProductData, SourceEvidence


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    product_url: str | None = None


class ChatAnswer(BaseModel):
    text: str
    intent: str
    confidence: Literal["high", "medium", "low"]
    limitations: list[str] = []


class ContentDraft(BaseModel):
    title: str
    content: str
    facts_used: list[str] = []
    claims_preserved: list[str] = []
    claims_not_introduced: list[str] = []


class ChatResponse(BaseModel):
    session_id: str
    answer: ChatAnswer
    product: ProductData | None = None
    evaluation: ProductEvaluation | None = None
    content_draft: ContentDraft | None = None
    evidence: list[SourceEvidence] = []
    suggested_actions: list[str] = []


class FetchRequest(BaseModel):
    url: str


class AppError(Exception):
    """Raised with a user-facing code + message."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)
