"""Grounded product discovery using Healf's public Shopify storefront catalog."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
import re
import time
from urllib.parse import quote_plus

import httpx

from ..models import ProductData, SourceEvidence
from ..navigation.healf_client import fetch

_CONFIG_TTL_SECONDS = 3600
_config_cache: tuple[str, str, float] | None = None

_STOREFRONT_QUERY = """
query SearchProducts($query: String!, $first: Int!) {
  products(first: $first, query: $query, sortKey: RELEVANCE) {
    nodes {
      handle
      title
      vendor
      productType
      tags
      availableForSale
      priceRange { minVariantPrice { amount currencyCode } }
    }
  }
}
"""

_TOPIC_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("protein bar", ("protein bar", "protein bars", "protein snack", "protein snacks")),
    ("collagen powder", ("collagen powder", "collagen powders", "collagen peptides")),
    ("sleep mask", ("sleep mask", "sleep masks", "eye mask", "eye masks")),
    ("electrolyte", ("electrolyte", "electrolytes", "hydration salts")),
    ("magnesium", ("magnesium",)),
    ("protein", ("protein", "proteins")),
    ("creatine", ("creatine",)),
    ("collagen", ("collagen",)),
    ("probiotic", ("probiotic", "probiotics", "gut health")),
    ("omega 3", ("omega 3", "omega-3", "fish oil")),
    ("vitamin d", ("vitamin d",)),
    ("sunscreen", ("sunscreen", "sun cream", "spf")),
    ("shampoo", ("shampoo", "shampoos", "hairbath", "hair wash")),
    ("organic", ("organic", "certified organic", "organically certified")),
    ("skincare", ("skincare", "skin care")),
    ("sleep", ("sleep",)),
)

_MATCH_ALIASES: dict[str, tuple[str, ...]] = {
    "protein bar": ("protein bar", "protein-bar", "bar"),
    "collagen powder": ("collagen", "peptide"),
    "sleep mask": ("sleep mask", "eye mask", "mask"),
    "electrolyte": ("electrolyte", "hydration", "hydrating", "salts"),
    "protein": ("protein", "amino"),
    "probiotic": ("probiotic", "gut"),
    "omega 3": ("omega", "fish oil"),
    "sunscreen": ("sunscreen", "sun cream", "spf"),
    "shampoo": ("shampoo", "hairbath", "hair wash"),
    "organic": ("organic",),
    "skincare": ("skincare", "skin care", "serum", "cleanser"),
}

_TITLE_STOPWORDS = {
    "and", "the", "with", "for", "pack", "variety", "bundle", "stack",
    "sample", "caps", "capsules", "tablets", "powder", "sachets", "servings",
}


@dataclass(frozen=True)
class ProductSuggestion:
    title: str
    vendor: str | None
    handle: str
    price: str | None
    available: bool
    price_amount: float | None = None
    product_type: str | None = None
    tags: tuple[str, ...] = ()

    @property
    def url(self) -> str:
        return f"https://healf.com/en-uk/products/{self.handle}"


async def recommend(
    product: ProductData,
    message: str,
    limit: int = 4,
) -> tuple[str, list[ProductSuggestion], list[SourceEvidence]]:
    """Return a shopper-friendly, catalog-grounded recommendation answer."""
    query = derive_search_query(product, message)
    suggestions = await _search_catalog(query, first=max(12, limit * 3))
    suggestions = [
        suggestion
        for suggestion in suggestions
        if suggestion.handle != product.handle and suggestion.available
    ]
    suggestions = _prefer_topic_matches(suggestions, query)

    price_limit = _requested_price_limit(message)
    if price_limit is not None:
        suggestions = [
            suggestion
            for suggestion in suggestions
            if suggestion.price_amount is not None and suggestion.price_amount <= price_limit
        ]
    if re.search(r"\bdifferent brand\b", message, re.IGNORECASE) and product.vendor:
        suggestions = [
            suggestion
            for suggestion in suggestions
            if not suggestion.vendor or suggestion.vendor.casefold() != product.vendor.casefold()
        ]
    suggestions = suggestions[:limit]

    if not suggestions:
        search_url = f"https://healf.com/en-uk/search?q={quote_plus(query)}"
        return (
            "I couldn't retrieve live alternatives just now. "
            f"[Search Healf for {query}]({search_url}) and send me any product link you want to analyse.",
            [],
            [],
        )

    qualifier = f" under **£{price_limit:g}**" if price_limit is not None else ""
    lines = [f"Here are some live Healf catalog matches for **{query}**{qualifier}:"]
    evidence: list[SourceEvidence] = []
    for index, suggestion in enumerate(suggestions, start=1):
        details = [part for part in (suggestion.vendor, suggestion.price) if part]
        suffix = f" - {' · '.join(details)}" if details else ""
        lines.append(f"{index}. [{suggestion.title}]({suggestion.url}){suffix}")
        evidence.append(
            SourceEvidence(
                field="product_recommendation",
                source_type="derived",
                source_url=suggestion.url,
                excerpt=" · ".join(
                    part for part in (suggestion.title, suggestion.vendor, suggestion.price) if part
                ),
                selector="Healf Storefront catalog search",
                confidence=0.9,
            )
        )
    lines.extend(
        [
            "",
            "These are related catalog matches, not personalised medical recommendations. "
            "Tell me what matters most - price, ingredients, dietary needs, format, or reviews - "
            "and I can help you narrow the choice.",
        ]
    )
    return "\n".join(lines), suggestions, evidence


async def discover(
    message: str,
    limit: int = 4,
) -> tuple[str, list[ProductSuggestion], list[SourceEvidence], str]:
    """Search the live Healf catalogue before a product has been selected."""
    query = derive_discovery_query(message)
    suggestions = await _search_catalog(query, first=max(12, limit * 3))
    suggestions = [suggestion for suggestion in suggestions if suggestion.available]
    suggestions = _prefer_topic_matches(suggestions, query, strict=True)

    price_limit = _requested_price_limit(message)
    if price_limit is not None:
        suggestions = [
            suggestion
            for suggestion in suggestions
            if suggestion.price_amount is not None and suggestion.price_amount <= price_limit
        ]
    suggestions = suggestions[:limit]

    if not suggestions:
        search_url = f"https://healf.com/en-uk/search?q={quote_plus(query)}"
        return (
            f"I couldn't find an in-stock catalogue match for **{query}**. "
            f"[Search Healf for {query}]({search_url}) and send me any product link you want to analyse.",
            [],
            [],
            query,
        )

    qualifier = f" under **£{price_limit:g}**" if price_limit is not None else ""
    lines = [f"Yes - here are some live Healf catalogue matches for **{query}**{qualifier}:"]
    evidence: list[SourceEvidence] = []
    for index, suggestion in enumerate(suggestions, start=1):
        details = [part for part in (suggestion.vendor, suggestion.price) if part]
        suffix = f" - {' · '.join(details)}" if details else ""
        lines.append(f"{index}. [{suggestion.title}]({suggestion.url}){suffix}")
        evidence.append(
            SourceEvidence(
                field="product_recommendation",
                source_type="derived",
                source_url=suggestion.url,
                excerpt=" · ".join(
                    part for part in (suggestion.title, suggestion.vendor, suggestion.price) if part
                ),
                selector="Healf Storefront catalog search",
                confidence=0.9,
            )
        )
    lines.extend(
        [
            "",
            "These are live catalogue matches, not personalised medical recommendations. "
            "Tell me about one of them, or narrow the search by price or dietary preference.",
        ]
    )
    return "\n".join(lines), suggestions, evidence, query


async def find_product_url(name: str) -> str | None:
    """Resolve a shopper-supplied product name to a confident Healf catalog match."""
    query = _normalise(name)
    if not query:
        return None
    suggestions = await _search_catalog(query, first=10)
    best: ProductSuggestion | None = None
    best_score = 0.0
    for suggestion in suggestions:
        candidate = _normalise(f"{suggestion.vendor or ''} {suggestion.title}")
        title = _normalise(suggestion.title)
        if query in {candidate, title}:
            score = 1.0
        elif query in candidate or title in query:
            score = 0.92
        else:
            query_tokens = set(query.split())
            candidate_tokens = set(candidate.split())
            token_score = (
                len(query_tokens & candidate_tokens) / len(query_tokens | candidate_tokens)
                if query_tokens and candidate_tokens
                else 0.0
            )
            score = max(token_score, SequenceMatcher(None, query, candidate).ratio())
        if score > best_score:
            best, best_score = suggestion, score
    return best.url if best and best_score >= 0.62 else None


def derive_search_query(product: ProductData, message: str) -> str:
    """Prefer an explicitly requested topic, otherwise infer one from the product."""
    message_norm = _normalise(message)
    for topic, aliases in _TOPIC_ALIASES:
        if any(_contains_phrase(message_norm, alias) for alias in aliases):
            return topic

    product_text = _normalise(" ".join(filter(None, (product.title, product.product_type))))
    for topic, aliases in _TOPIC_ALIASES:
        if any(_contains_phrase(product_text, alias) for alias in aliases):
            return topic

    vendor_tokens = set(_normalise(product.vendor or "").split())
    tokens = [
        token
        for token in product_text.split()
        if len(token) > 2 and token not in _TITLE_STOPWORDS and token not in vendor_tokens
    ]
    return " ".join(tokens[:3]) or (product.vendor or "wellbeing")


def derive_discovery_query(message: str) -> str:
    """Extract a useful catalogue topic from a natural shopping question."""
    message_norm = _normalise(message)
    candidate = re.sub(
        r"^(?:please )?(?:do you|does healf) (?:have|stock|sell|carry)(?: any)? ",
        "",
        message_norm,
    )
    candidate = re.sub(r"^(?:can you )?(?:show|find|recommend)(?: me)? ", "", candidate)
    candidate = re.sub(r"^(?:i am|i m) looking for ", "", candidate)
    candidate = re.sub(
        r"\s+(?:do )?(?:you|healf)\s+(?:have|stock|sell|carry)$",
        "",
        candidate,
    )
    tokens = [
        token
        for token in candidate.split()
        if token not in {
            "a", "an", "any", "please", "some", "instead", "product", "products",
            "item", "items", "option", "options",
        }
    ]
    query = " ".join(tokens[:5]) or "wellbeing"
    for topic, aliases in _TOPIC_ALIASES:
        if query in {_normalise(alias) for alias in aliases}:
            return topic
    return query


def _prefer_topic_matches(
    suggestions: list[ProductSuggestion], query: str, strict: bool = False
) -> list[ProductSuggestion]:
    aliases = _MATCH_ALIASES.get(query)
    available = [item for item in suggestions if "sample" not in item.title.lower()]
    if aliases:
        matched = [
            item
            for item in available
            if any(
                _normalise(alias)
                in _normalise(
                    f"{item.title} {item.handle} {item.product_type or ''} {' '.join(item.tags)}"
                )
                for alias in aliases
            )
        ]
    else:
        query_tokens = {_singular_token(token) for token in _normalise(query).split() if len(token) > 2}
        required = min(2, len(query_tokens))
        matched = []
        for item in available:
            item_tokens = {
                _singular_token(token)
                for token in _normalise(
                    f"{item.title} {item.handle} {item.product_type or ''} {' '.join(item.tags)}"
                ).split()
            }
            if len(query_tokens & item_tokens) >= required:
                matched.append(item)
    return matched if matched or strict else available


def _singular_token(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith(("ches", "shes", "xes", "zes")):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


async def _search_catalog(query: str, first: int) -> list[ProductSuggestion]:
    endpoint, token = await _storefront_config(query)
    timeout = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            endpoint,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Storefront-Access-Token": token,
            },
            json={
                "query": _STOREFRONT_QUERY,
                "variables": {"query": query, "first": min(first, 20)},
            },
        )
        response.raise_for_status()
        payload = response.json()
    nodes = payload.get("data", {}).get("products", {}).get("nodes", [])
    return [_suggestion_from_node(node) for node in nodes if isinstance(node, dict)]


async def _storefront_config(search_query: str) -> tuple[str, str]:
    global _config_cache
    now = time.monotonic()
    if _config_cache and now - _config_cache[2] < _CONFIG_TTL_SECONDS:
        return _config_cache[0], _config_cache[1]

    page = await fetch(f"https://healf.com/en-uk/search?q={quote_plus(search_query)}")
    endpoint, token = _parse_storefront_config(page.text)
    parsed = httpx.URL(endpoint)
    if parsed.scheme != "https" or parsed.host != "how2go.myshopify.com":
        raise ValueError("Unexpected Healf storefront endpoint")
    _config_cache = (endpoint, token, now)
    return endpoint, token


def _parse_storefront_config(html: str) -> tuple[str, str]:
    match = re.search(
        r'\\"store\\":\{\\"url\\":\\"([^\"]+)\\",\\"token\\":\\"([^\"]+)\\"',
        html,
    )
    if not match:
        raise ValueError("Healf storefront configuration was not found")
    return match.group(1), match.group(2)


def _suggestion_from_node(node: dict) -> ProductSuggestion:
    money = node.get("priceRange", {}).get("minVariantPrice", {}) or {}
    raw_amount = money.get("amount")
    try:
        price_amount = float(raw_amount) if raw_amount is not None else None
    except (TypeError, ValueError):
        price_amount = None
    return ProductSuggestion(
        title=str(node.get("title") or "Untitled product"),
        vendor=str(node["vendor"]) if node.get("vendor") else None,
        handle=str(node.get("handle") or ""),
        price=_format_money(money.get("amount"), money.get("currencyCode")),
        available=bool(node.get("availableForSale")),
        price_amount=price_amount,
        product_type=str(node["productType"]) if node.get("productType") else None,
        tags=tuple(str(tag) for tag in (node.get("tags") or []) if tag),
    )


def _requested_price_limit(message: str) -> float | None:
    match = re.search(
        r"\b(?:under|below|less than|max(?:imum)?(?: of)?)\s*(?:£|gbp\s*)?(\d+(?:\.\d+)?)",
        message,
        re.IGNORECASE,
    )
    return float(match.group(1)) if match else None


def _format_money(amount: object, currency: object) -> str | None:
    if amount is None:
        return None
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        return None
    symbols = {"GBP": "£", "EUR": "€", "USD": "$"}
    code = str(currency or "GBP")
    rendered = f"{value:.2f}"
    return f"{symbols.get(code, code + ' ')}{rendered}"


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(rf"\b{re.escape(_normalise(phrase))}\b", text))
