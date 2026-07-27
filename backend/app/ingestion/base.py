"""Shared types for ingestion parsers.

Each parser returns a Fragment: a partial mapping of ProductData field names to
values, plus the evidence and warnings it produced. The merger combines
fragments using source precedence (PRD 15).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..models import SourceEvidence, SourceType


@dataclass
class Fragment:
    source_type: SourceType
    fields: dict = field(default_factory=dict)
    evidence: list[SourceEvidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def set(
        self,
        name: str,
        value,
        source_url: str,
        excerpt: str | None = None,
        selector: str | None = None,
        confidence: float = 0.8,
    ) -> None:
        if value is None or value == "" or value == [] or value == {}:
            return
        self.fields[name] = value
        self.evidence.append(
            SourceEvidence(
                field=name,
                source_type=self.source_type,
                source_url=source_url,
                excerpt=excerpt,
                selector=selector,
                confidence=confidence,
            )
        )
