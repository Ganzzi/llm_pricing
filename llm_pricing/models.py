"""Pydantic data models for the LLM pricing package."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

# =============================================================================
# Rate Limiter Models (Model-Based!)
# =============================================================================


class ModelRateLimits(BaseModel):
    """
    Rate limits for a specific model on a specific tier.

    Example: Claude Sonnet 4.5 on "free" tier has RPM=10, TPM=1M

    Attributes:
        rpm: Requests per minute
        rpd: Requests per day
        tpm: Tokens per minute (total)
        tpd: Tokens per day
        itpm: Input tokens per minute
        otpm: Output tokens per minute
    """

    rpm: Optional[int] = Field(None, description="Requests per minute")
    rpd: Optional[int] = Field(None, description="Requests per day")
    tpm: Optional[int] = Field(None, description="Tokens per minute (total)")
    tpd: Optional[int] = Field(None, description="Tokens per day")
    itpm: Optional[int] = Field(None, description="Input tokens per minute")
    otpm: Optional[int] = Field(None, description="Output tokens per minute")

    @model_validator(mode="after")
    def check_at_least_one_limit(self) -> ModelRateLimits:
        """Ensure at least one rate limit is specified."""
        if not any(
            x is not None for x in [self.rpm, self.rpd, self.tpm, self.tpd, self.itpm, self.otpm]
        ):
            raise ValueError("At least one rate limit must be specified")
        return self


# =============================================================================
# Tiered Pricing Models (Like Claude Sonnet 4.5)
# =============================================================================


class PriceTier(BaseModel):
    """
    A pricing tier for token-based pricing.

    Example: After 200K tokens, price changes from $3 to $6 per 1M tokens.

    Attributes:
        start: Token count where this tier starts
        price: Price per 1M tokens in this tier
    """

    start: int = Field(..., description="Token count where this tier starts")
    price: Decimal = Field(..., description="Price per 1M tokens in this tier")

    @field_validator("start")
    @classmethod
    def validate_start(cls, v: int) -> int:
        if v < 0:
            raise ValueError("start must be non-negative")
        return v

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("price must be non-negative")
        return v


class TieredPrice(BaseModel):
    """
    Price that varies based on token count (tiered pricing).

    Example from Claude Sonnet 4.5:
    - Base: $3 per 1M tokens
    - After 200K tokens: $6 per 1M tokens

    YAML representation:
        input_mtok:
          base: 3

    Attributes:
        base: Base price per 1M tokens
        tiers: Additional pricing tiers (sorted by start)
    """

    base: Decimal = Field(..., description="Base price per 1M tokens")
    tiers: List[PriceTier] = Field(
        default_factory=list, description="Additional pricing tiers (sorted by start)"
    )

    @model_validator(mode="after")
    def sort_tiers(self) -> TieredPrice:
        """Ensure tiers are sorted by start token count."""
        self.tiers = sorted(self.tiers, key=lambda t: t.start)
        return self

    def get_price_at(self, tokens: int) -> Decimal:
        """Get the price per 1M tokens at a given token count."""
        price = self.base
        for tier in self.tiers:
            if tokens >= tier.start:
                price = tier.price
        return price

    def calculate_cost(self, tokens: int) -> Decimal:
        """
        Calculate total cost for a given number of tokens.

        Example: 300K tokens with base=$3, tier at 200K=$6
        - First 200K: 200,000 × $3 / 1M = $0.60
        - Remaining 100K: 100,000 × $6 / 1M = $0.60
        - Total: $1.20

        Args:
            tokens: Number of tokens

        Returns:
            Total cost as Decimal
        """
        if tokens <= 0:
            return Decimal(0)

        if not self.tiers:
            # Simple case: no tiers, just base price
            return Decimal(tokens) * self.base / Decimal(1_000_000)

        total_cost = Decimal(0)
        remaining_tokens = tokens
        current_price = self.base
        previous_boundary = 0

        # Process each tier
        for tier in self.tiers:
            if remaining_tokens <= 0:
                break

            # Tokens at current price level (before this tier)
            tokens_at_current_price = min(remaining_tokens, tier.start - previous_boundary)
            total_cost += Decimal(tokens_at_current_price) * current_price / Decimal(1_000_000)
            remaining_tokens -= tokens_at_current_price

            # Move to next tier
            current_price = tier.price
            previous_boundary = tier.start

        # Handle remaining tokens at final tier price
        if remaining_tokens > 0:
            total_cost += Decimal(remaining_tokens) * current_price / Decimal(1_000_000)

        return total_cost


# Type alias for price fields that can be simple or tiered
PriceValue = Union[Decimal, TieredPrice]


# =============================================================================
# Model Pricing
# =============================================================================


class ModelPrice(BaseModel):
    """
    Pricing configuration for a model on a specific tier.

    Supports both simple pricing (Decimal) and tiered pricing (TieredPrice).

    Example simple:
        input_mtok: 3.00
        output_mtok: 15.00

    Example tiered (Claude Sonnet 4.5):
        input_mtok:
          base: 3

    Attributes:
        input_mtok: Price per 1M input tokens (simple or tiered)
        output_mtok: Price per 1M output tokens (simple or tiered)
        cache_write_mtok: Price per 1M cache write tokens (optional)
        cache_read_mtok: Price per 1M cache read tokens (optional)
        credit_rate_per_mtok: Platform credit rate per 1M total tokens,
            blended (optional, admin-configured)
    """

    input_mtok: PriceValue = Field(..., description="Price per 1M input tokens")
    output_mtok: PriceValue = Field(..., description="Price per 1M output tokens")
    cache_write_mtok: Optional[PriceValue] = Field(
        None, description="Price per 1M cache write tokens"
    )
    cache_read_mtok: Optional[PriceValue] = Field(
        None, description="Price per 1M cache read tokens"
    )
    credit_rate_per_mtok: Optional[Decimal] = Field(
        None,
        description="Platform credit rate per 1M total tokens (blended); admin-configured, not API-sourced",
    )

    @field_validator("credit_rate_per_mtok")
    @classmethod
    def validate_credit_rate(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("credit_rate_per_mtok must be non-negative")
        return v

    def calculate_input_cost(self, tokens: int) -> Decimal:
        """Calculate cost for input tokens."""
        return self._calculate_cost(self.input_mtok, tokens)

    def calculate_output_cost(self, tokens: int) -> Decimal:
        """Calculate cost for output tokens."""
        return self._calculate_cost(self.output_mtok, tokens)

    def calculate_cache_write_cost(self, tokens: int) -> Decimal:
        """Calculate cost for cache write tokens."""
        if self.cache_write_mtok is None:
            return Decimal(0)
        return self._calculate_cost(self.cache_write_mtok, tokens)

    def calculate_cache_read_cost(self, tokens: int) -> Decimal:
        """Calculate cost for cache read tokens."""
        if self.cache_read_mtok is None:
            return Decimal(0)
        return self._calculate_cost(self.cache_read_mtok, tokens)

    def _calculate_cost(self, price: PriceValue, tokens: int) -> Decimal:
        """Calculate cost based on simple or tiered price."""
        if isinstance(price, TieredPrice):
            return price.calculate_cost(tokens)
        else:
            # Simple price: tokens × price / 1M
            return Decimal(tokens) * price / Decimal(1_000_000)


# =============================================================================
# Model Information
# =============================================================================


class ModelInfo(BaseModel):
    """
    Complete model information including pricing and rate limiters per tier.

    Key insight: Rate limiters are model-based, not provider-based!

    Example:
        model_id: "claude-sonnet-4-5"
        pricing: ModelPrice(input_mtok=TieredPrice(...), ...)
        rate_limiters:
          free: ModelRateLimits(rpm=10, tpm=1_000_000)
          pro: ModelRateLimits(rpm=50, tpm=5_000_000)

    Attributes:
        model_id: Unique model identifier
        name: Human-readable model name
        provider_id: Parent provider ID
        description: Model description
        context_window: Maximum context window size
        match_patterns: Patterns for matching this model
        pricing: Pricing for this model (same across all tiers)
        rate_limiters: Rate limiters per tier (tier_id -> ModelRateLimits)
        is_available: Whether model is available
        prices_checked: Last price check date
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    model_id: str = Field(..., description="Unique model identifier")
    name: str = Field(..., description="Human-readable model name")
    provider_id: str = Field(..., description="Parent provider ID")
    description: str = Field("", description="Model description")
    context_window: int = Field(0, description="Maximum context window size")

    # Matching patterns (for model identification)
    match_patterns: List[str] = Field(
        default_factory=list, description="Patterns for matching this model"
    )

    # Pricing (same across all tiers)
    pricing: ModelPrice = Field(..., description="Pricing for this model")

    # Rate limiters per tier (MODEL-BASED!)
    rate_limiters: Dict[str, ModelRateLimits] = Field(
        default_factory=dict,
        description="Rate limiters per tier (tier_id -> ModelRateLimits)",
    )

    # Metadata
    is_available: bool = Field(True, description="Whether model is available")
    prices_checked: Optional[date] = Field(None, description="Last price check date")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def get_rate_limits(self, tier_id: str) -> Optional[ModelRateLimits]:
        """Get rate limits for a specific tier."""
        if tier_id in self.rate_limiters:
            return self.rate_limiters[tier_id]
        return self.rate_limiters.get("default")


# =============================================================================
# Provider Tier
# =============================================================================


class ProviderTier(BaseModel):
    """
    A tier within a provider (Free, Pro, Enterprise, etc.).

    Note: Rate limiters are NOT stored here - they're on ModelInfo!
    This tier just defines the tier's existence and metadata.

    Attributes:
        tier_id: Unique tier identifier
        name: Human-readable tier name
        description: Tier description
        is_available: Whether tier is available
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    tier_id: str = Field(..., description="Unique tier identifier")
    name: str = Field(..., description="Human-readable tier name")
    description: str = Field("", description="Tier description")

    # Metadata
    is_available: bool = Field(True, description="Whether tier is available")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Provider
# =============================================================================


class Provider(BaseModel):
    """
    A provider (OpenAI, Anthropic, etc.) with tiers and models.

    Example:
        Provider: Anthropic
        ├── Tiers: {free, pro, enterprise}
        └── Models:
            ├── claude-sonnet-4-5 (with pricing and rate_limiters per tier)
            └── ...

    Attributes:
        provider_id: Unique provider identifier
        name: Human-readable provider name
        api_endpoint_pattern: Regex for API URL matching
        documentation_url: Pricing documentation URL
        description: Provider description
        tiers: Available tiers (tier_id -> ProviderTier)
        models: Models (model_id -> ModelInfo)
        is_available: Whether provider is available
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    provider_id: str = Field(..., description="Unique provider identifier")
    name: str = Field(..., description="Human-readable provider name")
    api_endpoint_pattern: str = Field("", description="Regex for API URL matching")
    documentation_url: str = Field("", description="Pricing documentation URL")
    description: str = Field("", description="Provider description")

    # Tiers available for this provider
    tiers: Dict[str, ProviderTier] = Field(
        default_factory=dict, description="Available tiers (tier_id -> ProviderTier)"
    )

    # Models for this provider
    models: Dict[str, ModelInfo] = Field(
        default_factory=dict, description="Models (model_id -> ModelInfo)"
    )

    # Metadata
    is_available: bool = Field(True, description="Whether provider is available")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Get a model by ID."""
        return self.models.get(model_id)

    def get_tier(self, tier_id: str) -> Optional[ProviderTier]:
        """Get a tier by ID."""
        return self.tiers.get(tier_id)

    def ensure_default_tier(self) -> None:
        """Ensure the provider has a default tier."""
        if "default" not in self.tiers:
            self.tiers["default"] = ProviderTier(
                tier_id="default", name="Default", description="Default tier"
            )


# =============================================================================
# Root Database
# =============================================================================


class PricingDatabase(BaseModel):
    """
    Root container for all pricing data.

    This is the top-level object that gets serialized to JSON.

    Attributes:
        version: Schema version
        last_sync: Last sync timestamp
        metadata: Custom metadata
        providers: All providers (provider_id -> Provider)
    """

    version: str = Field("1.0", description="Schema version")
    last_sync: Optional[datetime] = Field(None, description="Last sync timestamp")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Custom metadata")
    providers: Dict[str, Provider] = Field(
        default_factory=dict, description="All providers (provider_id -> Provider)"
    )

    def get_provider(self, provider_id: str) -> Optional[Provider]:
        """Get a provider by ID."""
        return self.providers.get(provider_id)

    def get_model(self, provider_id: str, model_id: str) -> Optional[ModelInfo]:
        """Get a model by provider and model ID."""
        provider = self.get_provider(provider_id)
        if provider:
            return provider.get_model(model_id)
        return None


# =============================================================================
# Export All
# =============================================================================

__all__ = [
    # Rate limiters
    "ModelRateLimits",
    # Pricing
    "PriceTier",
    "TieredPrice",
    "PriceValue",
    "ModelPrice",
    # Model and Provider
    "ModelInfo",
    "ProviderTier",
    "Provider",
    # Database
    "PricingDatabase",
]
