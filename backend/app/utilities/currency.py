"""Money parsing/formatting."""
from __future__ import annotations

from ..models import Money

SYMBOLS = {"GBP": "£", "USD": "$", "EUR": "€"}


def make_money(amount: float | str | None, currency: str = "GBP") -> Money | None:
    if amount is None or amount == "":
        return None
    try:
        val = float(amount)
    except (ValueError, TypeError):
        return None
    sym = SYMBOLS.get(currency.upper(), "")
    return Money(amount=val, currency=currency.upper(), formatted=f"{sym}{val:.2f}")
