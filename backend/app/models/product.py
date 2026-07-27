"""Normalized product data models (PRD section 12)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal[
    "shopify_json",
    "json_ld",
    "embedded_json",
    "html",
    "review_widget",
    "derived",
]


class SourceEvidence(BaseModel):
    field: str
    source_type: SourceType
    source_url: str
    excerpt: str | None = None
    selector: str | None = None
    confidence: float = Field(ge=0, le=1)


class Money(BaseModel):
    amount: float
    currency: str = "GBP"
    formatted: str | None = None


class ProductImage(BaseModel):
    url: str
    alt_text: str | None = None
    width: int | None = None
    height: int | None = None
    position: int | None = None
    is_primary: bool = False


class SellingPlan(BaseModel):
    id: str | None = None
    name: str | None = None
    price: Money | None = None
    discount_percent: float | None = None
    description: str | None = None


class ProductVariant(BaseModel):
    id: str | None = None
    title: str | None = None
    sku: str | None = None
    available: bool | None = None
    price: Money | None = None
    compare_at_price: Money | None = None
    options: dict[str, str] = {}
    selling_plans: list[SellingPlan] = []


class ReviewSummary(BaseModel):
    present: bool | None = None
    count: int | None = None
    average_rating: float | None = None
    provider: str | None = None
    full_review_text_ingested: bool = False


class SeoData(BaseModel):
    title: str | None = None
    description: str | None = None
    canonical_url: str | None = None


class ProductData(BaseModel):
    source_url: str
    canonical_url: str | None = None
    retrieved_at: datetime
    locale: str | None = None
    handle: str

    title: str | None = None
    vendor: str | None = None
    product_type: str | None = None

    description_html: str | None = None
    description_text: str | None = None
    benefits: list[str] = []
    ingredients_raw: str | None = None
    ingredient_groups: dict[str, list[str]] = {}
    suggested_use: str | None = None
    warnings: list[str] = []

    one_time_price: Money | None = None
    compare_at_price: Money | None = None
    subscription_price: Money | None = None
    subscription_savings_percent: float | None = None

    available: bool | None = None
    selected_variant_id: str | None = None
    variants: list[ProductVariant] = []
    selling_plans: list[SellingPlan] = []

    reviews: ReviewSummary = ReviewSummary()
    images: list[ProductImage] = []
    seo: SeoData = SeoData()

    evidence: list[SourceEvidence] = []
    extraction_warnings: list[str] = []
