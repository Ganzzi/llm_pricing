"""Tiered pricing calculator."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from .types import TierBreakdown

if TYPE_CHECKING:
    from ..models import TieredPrice


@dataclass
class _TierData:
    """Internal class for tier data during calculation."""

    start: int
    price: Decimal


def calculate_tiered_cost(
    tokens: int,
    tiered_price: TieredPrice,
    cumulative_tokens: int = 0,
) -> tuple[Decimal, list[TierBreakdown]]:
    """Calculate cost using tiered pricing.

    Supports both flat pricing (base only) and tiered pricing with multiple
    price tiers. Calculates which tier each token falls into and applies
    the appropriate price.

    Args:
        tokens: Number of tokens to price
        tiered_price: TieredPrice model with base and optional tiers
        cumulative_tokens: Previously consumed tokens for tier tracking

    Returns:
        Tuple of (total_cost, breakdown_list)

    Example:
        For Claude Sonnet 4.5 with tiers:
        - Base: $3 per 1M tokens (0-200K)
        - Tier: $6 per 1M tokens (200K+)

        300K tokens would be:
        - First 200K: 200,000 × $3 / 1M = $0.60
        - Next 100K: 100,000 × $6 / 1M = $0.60
        - Total: $1.20
    """
    if tokens == 0:
        return Decimal("0"), []

    # If no tiers defined, use flat base rate
    if not tiered_price.tiers:
        cost = _flat_cost(tokens, tiered_price.base)
        breakdown = [
            TierBreakdown(
                tier_start=0,
                tier_end=None,
                price_per_million=tiered_price.base,
                tokens=tokens,
                cost=cost,
            )
        ]
        return cost, breakdown

    # Build complete tier list (base + additional tiers)
    all_tiers = _build_tier_list(tiered_price)

    total_cost = Decimal("0")
    breakdown: list[TierBreakdown] = []
    remaining_tokens = tokens
    current_position = cumulative_tokens

    for i, tier in enumerate(all_tiers):
        if remaining_tokens <= 0:
            break

        # Find the end of this tier
        tier_start = tier.start
        if i + 1 < len(all_tiers):
            tier_end = all_tiers[i + 1].start
        else:
            tier_end = None

        # How many tokens in this tier?
        if tier_end is not None:
            tokens_in_tier = min(remaining_tokens, tier_end - current_position)
        else:
            tokens_in_tier = remaining_tokens

        # Calculate cost for tokens in this tier
        tier_cost = _flat_cost(tokens_in_tier, tier.price)
        total_cost += tier_cost

        # Record breakdown
        breakdown.append(
            TierBreakdown(
                tier_start=tier_start,
                tier_end=tier_end,
                price_per_million=tier.price,
                tokens=tokens_in_tier,
                cost=tier_cost,
            )
        )

        remaining_tokens -= tokens_in_tier
        current_position += tokens_in_tier

    return total_cost, breakdown


def _flat_cost(tokens: int, price_per_million: Decimal) -> Decimal:
    """Calculate flat-rate cost for tokens.

    Args:
        tokens: Number of tokens
        price_per_million: Price per 1 million tokens

    Returns:
        Cost in dollars (as Decimal)
    """
    return (Decimal(tokens) / Decimal("1000000")) * price_per_million


def _build_tier_list(tiered_price: TieredPrice) -> list[_TierData]:
    """Build complete sorted tier list including implicit base tier.

    The base price applies from 0 to the first tier threshold.
    Additional tiers are appended in order.

    Args:
        tiered_price: TieredPrice with base and optional tiers

    Returns:
        Sorted list of tiers with start points
    """
    tiers: list[_TierData] = []

    # Add base tier (0 to first custom tier, or unlimited)
    if tiered_price.tiers:
        tiers.append(_TierData(start=0, price=tiered_price.base))
    else:
        # No tiers, just return base
        tiers.append(_TierData(start=0, price=tiered_price.base))

    # Add all custom tiers
    for tier in tiered_price.tiers:
        tiers.append(_TierData(start=tier.start, price=tier.price))

    # Sort by start
    tiers.sort(key=lambda t: t.start)

    return tiers
