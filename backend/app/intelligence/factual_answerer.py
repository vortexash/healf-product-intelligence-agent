"""Deterministic factual answers from ProductData (PRD 17). No LLM required."""
from __future__ import annotations

import re

from ..models import ChatAnswer, ProductData
from ..utilities import normalize

# Ingredient alias map (PRD 17.2). Keys are normalized query terms.
INGREDIENT_ALIASES: dict[str, list[str]] = {
    "vitamin d": ["vitamin d", "vitamin d3", "vitamin d2", "cholecalciferol", "ergocalciferol"],
    "vitamin c": ["vitamin c", "ascorbic acid", "sodium ascorbate", "ascorbate"],
    "vitamin b12": ["vitamin b12", "cobalamin", "methylcobalamin", "cyanocobalamin"],
    "magnesium": ["magnesium", "magnesium malate", "magnesium citrate", "magnesium glycinate", "magnesium bisglycinate"],
    "potassium": ["potassium", "potassium chloride", "potassium citrate"],
    "sodium": ["sodium", "salt", "sodium chloride"],
    "caffeine": ["caffeine", "anhydrous caffeine"],
    "zinc": ["zinc", "zinc citrate", "zinc picolinate"],
    "iron": ["iron", "ferrous", "ferric"],
    "omega 3": ["omega 3", "omega-3", "epa", "dha", "fish oil"],
    "protein": ["protein", "whey", "casein", "pea protein"],
    "collagen": ["collagen", "collagen peptides", "hydrolysed collagen"],
    "creatine": ["creatine", "creatine monohydrate"],
}


def _aliases_for(term: str) -> list[str]:
    n = normalize(term)
    if n in INGREDIENT_ALIASES:
        return INGREDIENT_ALIASES[n]
    # Prefix / partial match against known keys (e.g. "vitamin d3" -> vitamin d).
    for key, al in INGREDIENT_ALIASES.items():
        if n == key or n in al or key in n:
            return al
    return [n]


def _ingredient_haystack(p: ProductData) -> str:
    parts = [p.ingredients_raw or ""]
    for group in p.ingredient_groups.values():
        parts.extend(group)
    return normalize(" ".join(parts))


def answer_ingredient(p: ProductData, term: str | None) -> ChatAnswer:
    if not term:
        term = "that ingredient"
    if not p.ingredients_raw and not p.ingredient_groups:
        return ChatAnswer(
            text=(
                f"I could not find an ingredients section on the live page, so I cannot confirm "
                f"whether **{term}** is present. This is an *unknown*, not an absence."
            ),
            intent="ingredient_lookup",
            confidence="low",
            limitations=["No ingredients section was extracted from the public page."],
        )
    aliases = _aliases_for(term)
    haystack = _ingredient_haystack(p)
    matched = [a for a in aliases if re.search(r"\b" + re.escape(a) + r"\b", haystack)]
    excerpt = (p.ingredients_raw or "")[:400]
    if matched:
        pretty = ", ".join(sorted(set(matched)))
        return ChatAnswer(
            text=(
                f"**Yes — {term} is listed** in the ingredients.\n\n"
                f"Matched terms: _{pretty}_.\n\n"
                f"Ingredient excerpt: “{excerpt}…”"
            ),
            intent="ingredient_lookup",
            confidence="high",
            limitations=["Formulations can change; always check the physical label."],
        )
    return ChatAnswer(
        text=(
            f"**{term} is not listed** in the ingredients available on the live page.\n\n"
            f"(That means it was not found in the published list — not a guarantee the product "
            f"is free from it.)\n\nIngredient excerpt: “{excerpt}…”"
        ),
        intent="ingredient_lookup",
        confidence="high",
        limitations=[
            "Based only on the ingredients published on the current public page.",
            "Formulations can change; check the physical label.",
        ],
    )


def answer_reviews(p: ProductData) -> ChatAnswer:
    r = p.reviews
    if r.present and (r.count or r.average_rating):
        bits = ["**Yes, this product has reviews.**"]
        if r.count is not None:
            bits.append(f"There are **{r.count:,} reviews**.")
        if r.average_rating is not None:
            bits.append(f"Average rating: **{r.average_rating}/5**.")
        return ChatAnswer(
            text=" ".join(bits),
            intent="review_lookup",
            confidence="high",
            limitations=["Only aggregate review data was ingested — individual review text was not."],
        )
    if r.present is False:
        return ChatAnswer(text="This product does not appear to have any reviews on the page.", intent="review_lookup", confidence="medium")
    return ChatAnswer(
        text="I could not determine review information from the live page.",
        intent="review_lookup",
        confidence="low",
        limitations=["Review data could not be retrieved."],
    )


def answer_price(p: ProductData) -> ChatAnswer:
    if not p.one_time_price:
        return ChatAnswer(text="I could not find pricing on the live page.", intent="price_lookup", confidence="low")
    lines = [f"**One-time price:** {p.one_time_price.formatted}"]
    if p.compare_at_price and p.compare_at_price.amount > p.one_time_price.amount:
        lines.append(f"~~{p.compare_at_price.formatted}~~ (was)")
    if p.subscription_price:
        save = f" (save {p.subscription_savings_percent:.0f}%)" if p.subscription_savings_percent else ""
        lines.append(f"**Subscription price:** {p.subscription_price.formatted}{save}")
    if p.selected_variant_id:
        sel = next((v for v in p.variants if v.id == p.selected_variant_id), None)
        if sel and sel.title:
            lines.append(f"**Selected variant:** {sel.title}")
    lines.append(f"**Availability:** {'In stock' if p.available else 'Unavailable' if p.available is False else 'Unknown'}")
    return ChatAnswer(text="\n".join(lines), intent="price_lookup", confidence="high")


def answer_subscription(p: ProductData) -> ChatAnswer:
    if not p.subscription_price and not p.selling_plans:
        return ChatAnswer(text="No subscription option was found for this product on the live page.", intent="subscription_lookup", confidence="medium")
    lines = []
    if p.one_time_price:
        lines.append(f"**One-time:** {p.one_time_price.formatted}")
    if p.subscription_price:
        save = f" — {p.subscription_savings_percent:.0f}% off" if p.subscription_savings_percent else ""
        lines.append(f"**Subscription:** {p.subscription_price.formatted}{save}")
    if p.selling_plans:
        names = ", ".join(sp.name for sp in p.selling_plans if sp.name)
        if names:
            lines.append(f"**Plans:** {names}")
    return ChatAnswer(text="\n".join(lines), intent="subscription_lookup", confidence="high")


def answer_availability(p: ProductData) -> ChatAnswer:
    if p.available is True:
        txt = "**In stock** and available to buy."
        conf = "high"
    elif p.available is False:
        txt = "This product appears to be **unavailable / out of stock**."
        conf = "high"
    else:
        txt = "Availability could not be determined from the live page."
        conf = "low"
    return ChatAnswer(text=txt, intent="availability_lookup", confidence=conf)


def answer_image_count(p: ProductData) -> ChatAnswer:
    n = len(p.images)
    alt = sum(1 for i in p.images if i.alt_text)
    txt = f"This page has **{n} product image{'s' if n != 1 else ''}**."
    if n:
        txt += f" Alt text is present on {alt}/{n}."
    return ChatAnswer(
        text=txt,
        intent="image_evaluation",
        confidence="high" if n else "low",
        limitations=["Image *content* was not visually inspected (no vision in the MVP)."],
    )
