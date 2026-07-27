"""Evaluation models (PRD 12.2)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvaluationCategory(BaseModel):
    key: str
    label: str
    score: int = Field(ge=0, le=100)
    status: Literal["strong", "good", "moderate", "weak", "unknown"]
    findings: list[str] = []
    evidence_fields: list[str] = []


class Recommendation(BaseModel):
    priority: int
    title: str
    rationale: str
    suggested_action: str
    evidence_fields: list[str] = []


class ProductEvaluation(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    summary: str
    categories: list[EvaluationCategory]
    recommendations: list[Recommendation]
    limitations: list[str] = []
    provisional: bool = False
