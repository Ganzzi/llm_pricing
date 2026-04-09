"""Types for pricing calculations."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class TokenUsage:
    """Token usage for a single request.

    Attributes:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cache_read_tokens: Number of tokens read from cache
        cache_creation_tokens: Number of tokens used for cache creation
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output, excluding cache)."""
        return self.input_tokens + self.output_tokens

    @property
    def total_with_cache(self) -> int:
        """Total tokens including cache operations."""
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )


@dataclass
class TierBreakdown:
    """Cost breakdown for a single pricing tier.

    Shows how many tokens were processed at a specific tier's price.

    Attributes:
        tier_start: Starting token count for this tier
        tier_end: Ending token count for this tier (None = unlimited)
        price_per_million: Price per million tokens in this tier
        tokens: Number of tokens processed in this tier
        cost: Cost for tokens in this tier
    """

    tier_start: int
    tier_end: Optional[int]  # None = unlimited
    price_per_million: Decimal
    tokens: int
    cost: Decimal


@dataclass
class CostBreakdown:
    """Detailed cost breakdown for a usage calculation.

    Includes individual costs for different token types and a detailed
    breakdown showing how tiered pricing was applied.

    Attributes:
        input_cost: Cost for input tokens
        output_cost: Cost for output tokens
        cache_read_cost: Cost for cache read tokens
        cache_creation_cost: Cost for cache creation tokens
        input_breakdown: Tier-by-tier breakdown for input tokens
        output_breakdown: Tier-by-tier breakdown for output tokens
        tier_multiplier: Multiplier from provider tier (default 1.0)
        tier_name: Name of the provider tier used (optional)
    """

    # Individual costs (before tier multiplier)
    input_cost: Decimal = Decimal("0")
    output_cost: Decimal = Decimal("0")
    cache_read_cost: Decimal = Decimal("0")
    cache_creation_cost: Decimal = Decimal("0")

    # Detailed breakdown for tiered pricing
    input_breakdown: list[TierBreakdown] = field(default_factory=list)
    output_breakdown: list[TierBreakdown] = field(default_factory=list)

    # Provider tier multiplier
    tier_multiplier: Decimal = Decimal("1.0")
    tier_name: Optional[str] = None

    @property
    def subtotal(self) -> Decimal:
        """Subtotal before tier multiplier."""
        return self.input_cost + self.output_cost + self.cache_read_cost + self.cache_creation_cost

    @property
    def total_cost(self) -> Decimal:
        """Total cost with tier multiplier applied."""
        return self.subtotal * self.tier_multiplier

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the cost breakdown.
        """
        return {
            "input_cost": str(self.input_cost),
            "output_cost": str(self.output_cost),
            "cache_read_cost": str(self.cache_read_cost),
            "cache_creation_cost": str(self.cache_creation_cost),
            "subtotal": str(self.subtotal),
            "tier_multiplier": str(self.tier_multiplier),
            "tier_name": self.tier_name,
            "total_cost": str(self.total_cost),
            "input_breakdown": [
                {
                    "tier_start": bd.tier_start,
                    "tier_end": bd.tier_end,
                    "price_per_million": str(bd.price_per_million),
                    "tokens": bd.tokens,
                    "cost": str(bd.cost),
                }
                for bd in self.input_breakdown
            ],
            "output_breakdown": [
                {
                    "tier_start": bd.tier_start,
                    "tier_end": bd.tier_end,
                    "price_per_million": str(bd.price_per_million),
                    "tokens": bd.tokens,
                    "cost": str(bd.cost),
                }
                for bd in self.output_breakdown
            ],
        }
