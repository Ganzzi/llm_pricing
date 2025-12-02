"""Cache cost calculator."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional


def calculate_cache_cost(
    cache_read_tokens: int,
    cache_creation_tokens: int,
    cache_read_price: Optional[Decimal],
    cache_creation_price: Optional[Decimal],
) -> tuple[Decimal, Decimal]:
    """Calculate cache-related costs.

    Cache pricing is always flat-rate (no tiering).

    Args:
        cache_read_tokens: Tokens read from cache
        cache_creation_tokens: Tokens used for cache creation
        cache_read_price: Price per million for cache read tokens
        cache_creation_price: Price per million for cache creation tokens

    Returns:
        Tuple of (cache_read_cost, cache_creation_cost)
    """
    cache_read_cost = Decimal("0")
    cache_creation_cost = Decimal("0")

    if cache_read_price is not None and cache_read_tokens > 0:
        cache_read_cost = (Decimal(cache_read_tokens) / Decimal("1000000")) * cache_read_price

    if cache_creation_price is not None and cache_creation_tokens > 0:
        cache_creation_cost = (
            Decimal(cache_creation_tokens) / Decimal("1000000")
        ) * cache_creation_price

    return cache_read_cost, cache_creation_cost
