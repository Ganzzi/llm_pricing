"""Main pricing engine."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Union

from ..models import ModelPrice, TieredPrice
from ..repository import PricingRepository
from .types import TokenUsage, CostBreakdown, TierBreakdown

if TYPE_CHECKING:
    from ..models import ModelInfo
else:
    from ..models import ModelInfo


def calculate_tiered_cost(
    tokens: int,
    tiered_price: TieredPrice,
    cumulative_tokens: int = 0,
) -> tuple[Decimal, list[TierBreakdown]]:
    """Import from tiered module."""
    from .tiered import calculate_tiered_cost as _calculate_tiered_cost

    return _calculate_tiered_cost(tokens, tiered_price, cumulative_tokens)


def calculate_cache_cost(
    cache_read_tokens: int,
    cache_creation_tokens: int,
    cache_read_price: Optional[Decimal],
    cache_creation_price: Optional[Decimal],
) -> tuple[Decimal, Decimal]:
    """Import from cache module."""
    from .cache import calculate_cache_cost as _calculate_cache_cost

    return _calculate_cache_cost(
        cache_read_tokens, cache_creation_tokens, cache_read_price, cache_creation_price
    )


class PricingEngine:
    """Engine for calculating LLM costs.

    Supports:
    - Flat-rate pricing
    - Tiered pricing (Claude Sonnet 4.5 style)
    - Cache read/creation costs
    - Provider tier multipliers

    Example:
        from llm_pricing.engine import PricingEngine, TokenUsage

        engine = PricingEngine(repository)
        usage = TokenUsage(input_tokens=10000, output_tokens=5000)
        result = engine.calculate(
            provider_id="anthropic",
            model_id="claude-sonnet-4-20250514",
            usage=usage,
            tier="pro",
        )
        print(f"Total cost: ${result.total_cost}")
    """

    def __init__(self, repository: PricingRepository):
        """Initialize pricing engine.

        Args:
            repository: PricingRepository instance with pricing data
        """
        self._repo = repository

    def calculate(
        self,
        provider_id: str,
        model_id: str,
        usage: TokenUsage,
        tier: Optional[str] = None,
    ) -> CostBreakdown:
        """Calculate cost for token usage.

        Retrieves model pricing information, applies tiered pricing logic,
        and returns a detailed cost breakdown.

        Args:
            provider_id: Provider ID (e.g., "anthropic")
            model_id: Model ID (e.g., "claude-sonnet-4-20250514")
            usage: TokenUsage with token counts
            tier: Optional tier ID (e.g., "pro"). Falls back to "default"

        Returns:
            CostBreakdown with detailed cost information

        Raises:
            ValueError: If provider or model not found
        """
        # Get model info
        model = self._repo.get_model(provider_id, model_id)
        if not model:
            raise ValueError(f"Model {provider_id}/{model_id} not found")

        # Use provided tier or default (not needed for pricing since it's direct)
        if tier is None:
            tier = "default"

        # Get pricing (now directly from model.pricing, not per-tier)
        pricing = model.pricing
        if not pricing:
            raise ValueError(f"No pricing found for {provider_id}/{model_id}")

        # Calculate input and output costs
        input_cost, input_breakdown = self._calculate_token_cost(
            usage.input_tokens, pricing.input_mtok
        )
        output_cost, output_breakdown = self._calculate_token_cost(
            usage.output_tokens, pricing.output_mtok
        )

        # Calculate cache costs
        cache_write_price = self._extract_price(pricing.cache_write_mtok)
        cache_read_price = self._extract_price(pricing.cache_read_mtok)

        cache_read_cost, cache_creation_cost = calculate_cache_cost(
            cache_read_tokens=usage.cache_read_tokens,
            cache_creation_tokens=usage.cache_creation_tokens,
            cache_read_price=cache_read_price,
            cache_creation_price=cache_write_price,
        )

        # Create breakdown
        breakdown = CostBreakdown(
            input_cost=input_cost,
            output_cost=output_cost,
            cache_read_cost=cache_read_cost,
            cache_creation_cost=cache_creation_cost,
            input_breakdown=input_breakdown,
            output_breakdown=output_breakdown,
            tier_multiplier=Decimal("1.0"),
            tier_name=tier,
        )

        return breakdown

    def _calculate_token_cost(
        self,
        tokens: int,
        pricing: Union[Decimal, TieredPrice],
    ) -> tuple[Decimal, list[TierBreakdown]]:
        """Calculate cost for tokens using flat or tiered pricing.

        Args:
            tokens: Number of tokens
            pricing: ModelPrice field (can be Decimal or TieredPrice)

        Returns:
            Tuple of (total_cost, breakdown_list)
        """
        if tokens == 0:
            return Decimal("0"), []

        if isinstance(pricing, TieredPrice):
            return calculate_tiered_cost(tokens, pricing)
        else:
            # Simple flat price
            cost = (Decimal(tokens) / Decimal("1000000")) * pricing
            return cost, []

    def _extract_price(self, price_value: Union[Decimal, TieredPrice, None]) -> Optional[Decimal]:
        """Extract simple price from either Decimal or TieredPrice.

        For TieredPrice, returns the base price.

        Args:
            price_value: Can be Decimal or TieredPrice

        Returns:
            Decimal price or None if not set
        """
        if price_value is None:
            return None
        if isinstance(price_value, TieredPrice):
            return price_value.base
        return price_value
