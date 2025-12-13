from __future__ import annotations

# Simple platform fee approximations; tune per provider & category
PLATFORM_FEES = {"ebay": 0.125, "tcgplayer": 0.14, "default": 0.12}  # 12.5%


def platform_fee(provider: str, price: float) -> float:
    r = PLATFORM_FEES.get((provider or "").lower(), PLATFORM_FEES["default"])
    return round(price * r, 2)


def effective_price(
    provider: str, price: float | None, shipping: float | None
) -> float | None:
    if price is None:
        return None
    ship = float(shipping or 0)
    fees = platform_fee(provider, float(price))
    return round(float(price) - ship - fees, 2)
