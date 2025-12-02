# Phase 1: Data Models

## Overview

This phase defines all Pydantic data models for the pricing package. The key insight is that **rate limiters are model-based, not provider-based**.

**Duration:** 2-3 days

---

## 🎯 Goals

- [ ] Define all core Pydantic models
- [ ] Support tiered pricing (like Claude Sonnet 4.5)
- [ ] Support model-based rate limiters per tier
- [ ] Create JSON schema for validation
- [ ] Write unit tests for serialization/deserialization

---

## 📊 Data Model Hierarchy

```
PricingDatabase (root)
├── version: str
├── last_sync: datetime | None
├── metadata: Dict[str, str]
└── providers: Dict[str, Provider]
    └── Provider
        ├── provider_id: str
        ├── name: str
        ├── api_endpoint_pattern: str
        ├── documentation_url: str
        ├── description: str
        ├── tiers: Dict[str, ProviderTier]
        │   └── ProviderTier
        │       ├── tier_id: str
        │       ├── name: str
        │       └── description: str
        │       (NO rate limiters here - they're on models!)
        │
        └── models: Dict[str, ModelInfo]
            └── ModelInfo
                ├── model_id: str
                ├── name: str
                ├── description: str
                ├── context_window: int
                ├── match_patterns: List[str]
                │
                ├── pricing: Dict[str, ModelPrice]  ← Per tier
                │   └── ModelPrice
                │       ├── input_mtok: TieredPrice | Decimal
                │       ├── output_mtok: TieredPrice | Decimal
                │       ├── cache_write_mtok: TieredPrice | Decimal | None
                │       └── cache_read_mtok: TieredPrice | Decimal | None
                │
                └── rate_limiters: Dict[str, ModelRateLimits]  ← Per tier
                    └── ModelRateLimits
                        ├── rpm: int | None
                        ├── tpm: int | None
                        ├── tpd: int | None
                        ├── itpm: int | None
                        └── otpm: int | None
```

---

## 📝 Implementation

### File: `constants.py`

```python
"""Constants and enums for the pricing package."""

from enum import Enum

class RateLimiterType(str, Enum):
    """Types of rate limiters."""
    RPM = "rpm"    # Requests per minute
    TPM = "tpm"    # Tokens per minute (total)
    TPD = "tpd"    # Tokens per day
    ITPM = "itpm"  # Input tokens per minute
    OTPM = "otpm"  # Output tokens per minute

# Default tier ID
DEFAULT_TIER = "default"

# Schema version
SCHEMA_VERSION = "1.0"
```

---

### File: `types.py`

```python
"""Pydantic data models for the LLM pricing package."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

# =============================================================================
# Rate Limiter Models (Model-Based!)
# =============================================================================

class ModelRateLimits(BaseModel):
    """
    Rate limits for a specific model on a specific tier.
    
    Example: Claude Sonnet 4.5 on "free" tier has RPM=10, TPM=1M
    """
    rpm: Optional[int] = Field(None, description="Requests per minute")
    tpm: Optional[int] = Field(None, description="Tokens per minute (total)")
    tpd: Optional[int] = Field(None, description="Tokens per day")
    itpm: Optional[int] = Field(None, description="Input tokens per minute")
    otpm: Optional[int] = Field(None, description="Output tokens per minute")
    
    @model_validator(mode='after')
    def check_at_least_one_limit(self) -> 'ModelRateLimits':
        """Ensure at least one rate limit is specified."""
        if not any([self.rpm, self.tpm, self.tpd, self.itpm, self.otpm]):
            raise ValueError("At least one rate limit must be specified")
        return self


# =============================================================================
# Tiered Pricing Models (Like Claude Sonnet 4.5)
# =============================================================================

class PriceTier(BaseModel):
    """
    A pricing tier for token-based pricing.
    
    Example: After 200K tokens, price changes from $3 to $6 per 1M tokens.
    """
    start: int = Field(..., description="Token count where this tier starts")
    price: Decimal = Field(..., description="Price per 1M tokens in this tier")
    
    @field_validator('start')
    @classmethod
    def validate_start(cls, v: int) -> int:
        if v < 0:
            raise ValueError("start must be non-negative")
        return v
    
    @field_validator('price')
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
          tiers:
            - start: 200000
              price: 6
    """
    base: Decimal = Field(..., description="Base price per 1M tokens")
    tiers: List[PriceTier] = Field(
        default_factory=list,
        description="Additional pricing tiers (sorted by start)"
    )
    
    @model_validator(mode='after')
    def sort_tiers(self) -> 'TieredPrice':
        """Ensure tiers are sorted by start token count."""
        self.tiers = sorted(self.tiers, key=lambda t: t.start)
        return self
    
    def get_price_at(self, tokens: int) -> Decimal:
        """Get the price per 1M tokens at a given token count."""
        price = self.base
        for tier in self.tiers:
            if tokens >= tier.start:
                price = tier.price
            else:
                break
        return price
    
    def calculate_cost(self, tokens: int) -> Decimal:
        """
        Calculate total cost for a given number of tokens.
        
        Example: 300K tokens with base=$3, tier at 200K=$6
        - First 200K: 200,000 × $3 / 1M = $0.60
        - Remaining 100K: 100,000 × $6 / 1M = $0.60
        - Total: $1.20
        """
        if tokens <= 0:
            return Decimal(0)
        
        total_cost = Decimal(0)
        remaining_tokens = tokens
        previous_boundary = 0
        
        # Process each tier
        for tier in self.tiers:
            if remaining_tokens <= 0:
                break
            
            # Tokens at base price (before this tier)
            tokens_at_base = min(remaining_tokens, tier.start - previous_boundary)
            if tokens_at_base > 0 and previous_boundary == 0:
                # First segment at base price
                total_cost += Decimal(tokens_at_base) * self.base / Decimal(1_000_000)
                remaining_tokens -= tokens_at_base
            
            previous_boundary = tier.start
        
        # Handle remaining tokens at final tier price (or base if no tiers)
        if remaining_tokens > 0:
            final_price = self.tiers[-1].price if self.tiers else self.base
            total_cost += Decimal(remaining_tokens) * final_price / Decimal(1_000_000)
        
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
          tiers:
            - start: 200000
              price: 6
    """
    input_mtok: PriceValue = Field(..., description="Price per 1M input tokens")
    output_mtok: PriceValue = Field(..., description="Price per 1M output tokens")
    cache_write_mtok: Optional[PriceValue] = Field(
        None, description="Price per 1M cache write tokens"
    )
    cache_read_mtok: Optional[PriceValue] = Field(
        None, description="Price per 1M cache read tokens"
    )
    
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
        pricing:
          default: ModelPrice(input_mtok=TieredPrice(...), ...)
          enterprise: ModelPrice(input_mtok=Decimal("2.5"), ...)
        rate_limiters:
          free: ModelRateLimits(rpm=10, tpm=1_000_000)
          pro: ModelRateLimits(rpm=50, tpm=5_000_000)
    """
    model_id: str = Field(..., description="Unique model identifier")
    name: str = Field(..., description="Human-readable model name")
    provider_id: str = Field(..., description="Parent provider ID")
    description: str = Field("", description="Model description")
    context_window: int = Field(0, description="Maximum context window size")
    
    # Matching patterns (for model identification)
    match_patterns: List[str] = Field(
        default_factory=list,
        description="Patterns for matching this model"
    )
    
    # Pricing per tier
    pricing: Dict[str, ModelPrice] = Field(
        default_factory=dict,
        description="Pricing per tier (tier_id -> ModelPrice)"
    )
    
    # Rate limiters per tier (MODEL-BASED!)
    rate_limiters: Dict[str, ModelRateLimits] = Field(
        default_factory=dict,
        description="Rate limiters per tier (tier_id -> ModelRateLimits)"
    )
    
    # Metadata
    is_available: bool = Field(True, description="Whether model is available")
    prices_checked: Optional[date] = Field(None, description="Last price check date")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def get_pricing(self, tier_id: str) -> Optional[ModelPrice]:
        """Get pricing for a specific tier with fallback to default."""
        if tier_id in self.pricing:
            return self.pricing[tier_id]
        return self.pricing.get("default")
    
    def get_rate_limits(self, tier_id: str) -> Optional[ModelRateLimits]:
        """Get rate limits for a specific tier with fallback to default."""
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
            ├── claude-haiku-4-5
            └── ...
    """
    provider_id: str = Field(..., description="Unique provider identifier")
    name: str = Field(..., description="Human-readable provider name")
    api_endpoint_pattern: str = Field("", description="Regex for API URL matching")
    documentation_url: str = Field("", description="Pricing documentation URL")
    description: str = Field("", description="Provider description")
    
    # Tiers available for this provider
    tiers: Dict[str, ProviderTier] = Field(
        default_factory=dict,
        description="Available tiers (tier_id -> ProviderTier)"
    )
    
    # Models for this provider
    models: Dict[str, ModelInfo] = Field(
        default_factory=dict,
        description="Models (model_id -> ModelInfo)"
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
                tier_id="default",
                name="Default"
            )


# =============================================================================
# Root Database
# =============================================================================

class PricingDatabase(BaseModel):
    """
    Root container for all pricing data.
    
    This is the top-level object that gets serialized to JSON.
    """
    version: str = Field("1.0", description="Schema version")
    last_sync: Optional[datetime] = Field(None, description="Last sync timestamp")
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom metadata"
    )
    providers: Dict[str, Provider] = Field(
        default_factory=dict,
        description="All providers (provider_id -> Provider)"
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
    'ModelRateLimits',
    
    # Pricing
    'PriceTier',
    'TieredPrice',
    'PriceValue',
    'ModelPrice',
    
    # Model and Provider
    'ModelInfo',
    'ProviderTier',
    'Provider',
    
    # Database
    'PricingDatabase',
]
```

---

## 🧪 Test Cases

### File: `tests/test_types.py`

```python
"""Tests for Pydantic data models."""

import pytest
from decimal import Decimal
from datetime import date

from llm_pricing.types import (
    ModelRateLimits,
    PriceTier,
    TieredPrice,
    ModelPrice,
    ModelInfo,
    ProviderTier,
    Provider,
    PricingDatabase,
)


class TestModelRateLimits:
    """Tests for ModelRateLimits."""
    
    def test_valid_rate_limits(self):
        """Test creating valid rate limits."""
        limits = ModelRateLimits(rpm=10, tpm=1_000_000)
        assert limits.rpm == 10
        assert limits.tpm == 1_000_000
    
    def test_requires_at_least_one_limit(self):
        """Test that at least one limit is required."""
        with pytest.raises(ValueError, match="At least one rate limit"):
            ModelRateLimits()
    
    def test_all_limit_types(self):
        """Test all rate limit types."""
        limits = ModelRateLimits(
            rpm=60,
            tpm=100_000,
            tpd=1_000_000,
            itpm=80_000,
            otpm=20_000
        )
        assert limits.rpm == 60
        assert limits.tpm == 100_000
        assert limits.tpd == 1_000_000
        assert limits.itpm == 80_000
        assert limits.otpm == 20_000


class TestTieredPrice:
    """Tests for TieredPrice."""
    
    def test_simple_tiered_price(self):
        """Test tiered price like Claude Sonnet 4.5."""
        price = TieredPrice(
            base=Decimal("3"),
            tiers=[PriceTier(start=200_000, price=Decimal("6"))]
        )
        assert price.base == Decimal("3")
        assert len(price.tiers) == 1
    
    def test_calculate_cost_base_only(self):
        """Test cost calculation with base price only."""
        price = TieredPrice(base=Decimal("3"), tiers=[])
        
        # 1M tokens at $3/M = $3
        cost = price.calculate_cost(1_000_000)
        assert cost == Decimal("3")
    
    def test_calculate_cost_tiered(self):
        """Test cost calculation with tiered pricing."""
        price = TieredPrice(
            base=Decimal("3"),
            tiers=[PriceTier(start=200_000, price=Decimal("6"))]
        )
        
        # 300K tokens:
        # - First 200K at $3/M = $0.60
        # - Next 100K at $6/M = $0.60
        # - Total: $1.20
        cost = price.calculate_cost(300_000)
        assert cost == Decimal("1.20")
    
    def test_calculate_cost_under_first_tier(self):
        """Test cost when under first tier threshold."""
        price = TieredPrice(
            base=Decimal("3"),
            tiers=[PriceTier(start=200_000, price=Decimal("6"))]
        )
        
        # 100K tokens at $3/M = $0.30
        cost = price.calculate_cost(100_000)
        assert cost == Decimal("0.30")
    
    def test_tiers_are_sorted(self):
        """Test that tiers are automatically sorted."""
        price = TieredPrice(
            base=Decimal("1"),
            tiers=[
                PriceTier(start=300_000, price=Decimal("3")),
                PriceTier(start=100_000, price=Decimal("2")),
            ]
        )
        assert price.tiers[0].start == 100_000
        assert price.tiers[1].start == 300_000


class TestModelPrice:
    """Tests for ModelPrice."""
    
    def test_simple_pricing(self):
        """Test simple (non-tiered) pricing."""
        price = ModelPrice(
            input_mtok=Decimal("3"),
            output_mtok=Decimal("15")
        )
        
        # 1M input tokens = $3
        assert price.calculate_input_cost(1_000_000) == Decimal("3")
        
        # 1M output tokens = $15
        assert price.calculate_output_cost(1_000_000) == Decimal("15")
    
    def test_tiered_pricing(self):
        """Test tiered pricing calculation."""
        price = ModelPrice(
            input_mtok=TieredPrice(
                base=Decimal("3"),
                tiers=[PriceTier(start=200_000, price=Decimal("6"))]
            ),
            output_mtok=Decimal("15")
        )
        
        # 300K input tokens = $1.20 (tiered)
        assert price.calculate_input_cost(300_000) == Decimal("1.20")
        
        # 1M output tokens = $15 (simple)
        assert price.calculate_output_cost(1_000_000) == Decimal("15")
    
    def test_cache_pricing(self):
        """Test cache token pricing."""
        price = ModelPrice(
            input_mtok=Decimal("3"),
            output_mtok=Decimal("15"),
            cache_write_mtok=Decimal("3.75"),
            cache_read_mtok=Decimal("0.30")
        )
        
        # 1M cache write = $3.75
        assert price.calculate_cache_write_cost(1_000_000) == Decimal("3.75")
        
        # 1M cache read = $0.30
        assert price.calculate_cache_read_cost(1_000_000) == Decimal("0.30")
    
    def test_cache_pricing_none(self):
        """Test cache pricing when not set."""
        price = ModelPrice(
            input_mtok=Decimal("3"),
            output_mtok=Decimal("15")
        )
        
        # Should return 0 when cache pricing not set
        assert price.calculate_cache_write_cost(1_000_000) == Decimal("0")
        assert price.calculate_cache_read_cost(1_000_000) == Decimal("0")


class TestModelInfo:
    """Tests for ModelInfo."""
    
    def test_model_with_rate_limiters_per_tier(self):
        """Test model with rate limiters per tier."""
        model = ModelInfo(
            model_id="claude-sonnet-4-5",
            name="Claude Sonnet 4.5",
            provider_id="anthropic",
            pricing={
                "default": ModelPrice(
                    input_mtok=Decimal("3"),
                    output_mtok=Decimal("15")
                )
            },
            rate_limiters={
                "free": ModelRateLimits(rpm=10, tpm=1_000_000),
                "pro": ModelRateLimits(rpm=50, tpm=5_000_000),
            }
        )
        
        # Check rate limiters
        free_limits = model.get_rate_limits("free")
        assert free_limits.rpm == 10
        assert free_limits.tpm == 1_000_000
        
        pro_limits = model.get_rate_limits("pro")
        assert pro_limits.rpm == 50
        assert pro_limits.tpm == 5_000_000
    
    def test_pricing_fallback_to_default(self):
        """Test that pricing falls back to default tier."""
        model = ModelInfo(
            model_id="test",
            name="Test",
            provider_id="test",
            pricing={
                "default": ModelPrice(
                    input_mtok=Decimal("3"),
                    output_mtok=Decimal("15")
                )
            }
        )
        
        # Should return default pricing for unknown tier
        pricing = model.get_pricing("enterprise")
        assert pricing.input_mtok == Decimal("3")


class TestProvider:
    """Tests for Provider."""
    
    def test_provider_with_tiers_and_models(self):
        """Test complete provider setup."""
        provider = Provider(
            provider_id="anthropic",
            name="Anthropic",
            tiers={
                "free": ProviderTier(tier_id="free", name="Free"),
                "pro": ProviderTier(tier_id="pro", name="Professional"),
            },
            models={
                "claude-sonnet-4-5": ModelInfo(
                    model_id="claude-sonnet-4-5",
                    name="Claude Sonnet 4.5",
                    provider_id="anthropic",
                    pricing={
                        "default": ModelPrice(
                            input_mtok=Decimal("3"),
                            output_mtok=Decimal("15")
                        )
                    },
                    rate_limiters={
                        "free": ModelRateLimits(rpm=10, tpm=1_000_000),
                        "pro": ModelRateLimits(rpm=50, tpm=5_000_000),
                    }
                )
            }
        )
        
        # Get model
        model = provider.get_model("claude-sonnet-4-5")
        assert model is not None
        assert model.name == "Claude Sonnet 4.5"
        
        # Get tier
        tier = provider.get_tier("pro")
        assert tier is not None
        assert tier.name == "Professional"
    
    def test_ensure_default_tier(self):
        """Test ensuring default tier exists."""
        provider = Provider(
            provider_id="test",
            name="Test"
        )
        
        assert "default" not in provider.tiers
        provider.ensure_default_tier()
        assert "default" in provider.tiers


class TestPricingDatabase:
    """Tests for PricingDatabase."""
    
    def test_serialization(self):
        """Test serialization to JSON."""
        db = PricingDatabase(
            providers={
                "anthropic": Provider(
                    provider_id="anthropic",
                    name="Anthropic"
                )
            }
        )
        
        json_str = db.model_dump_json()
        assert "anthropic" in json_str
    
    def test_deserialization(self):
        """Test deserialization from JSON."""
        json_data = '''
        {
            "version": "1.0",
            "providers": {
                "anthropic": {
                    "provider_id": "anthropic",
                    "name": "Anthropic",
                    "tiers": {},
                    "models": {}
                }
            }
        }
        '''
        
        db = PricingDatabase.model_validate_json(json_data)
        assert db.version == "1.0"
        assert "anthropic" in db.providers
```

---

## 📋 Tasks Checklist

### Core Models
- [ ] Create `constants.py` with enums
- [ ] Create `types.py` with all models
- [ ] Implement `ModelRateLimits` class
- [ ] Implement `PriceTier` class
- [ ] Implement `TieredPrice` class with cost calculation
- [ ] Implement `ModelPrice` class
- [ ] Implement `ModelInfo` class with per-tier rate limiters
- [ ] Implement `ProviderTier` class
- [ ] Implement `Provider` class
- [ ] Implement `PricingDatabase` class

### Validation
- [ ] Add field validators for all models
- [ ] Add model validators for complex validation
- [ ] Test serialization/deserialization

### Tests
- [ ] Test `ModelRateLimits` validation
- [ ] Test `TieredPrice` cost calculation
- [ ] Test `ModelPrice` with simple and tiered pricing
- [ ] Test `ModelInfo` rate limiter per tier
- [ ] Test full database serialization roundtrip

### Documentation
- [ ] Add docstrings to all classes
- [ ] Add usage examples in docstrings
- [ ] Generate JSON schema

---

## 🔗 Dependencies

```toml
# pyproject.toml
[project]
dependencies = [
    "pydantic>=2.0",
]
```

---

## 📝 Notes

### Why Rate Limiters Are Model-Based

In real-world APIs, rate limits vary by:
1. **Model**: GPT-4 has different limits than GPT-3.5
2. **Tier**: Free tier has lower limits than Pro tier
3. **Account**: Enterprise accounts get custom limits

The structure `model.rate_limiters[tier_id]` captures this accurately:

```python
claude_sonnet = ModelInfo(
    model_id="claude-sonnet-4-5",
    rate_limiters={
        "free": ModelRateLimits(rpm=10, tpm=1_000_000),
        "pro": ModelRateLimits(rpm=50, tpm=5_000_000),
    }
)
```

### Why Tiered Pricing Matters

Claude Sonnet 4.5 has context-based pricing:
- First 200K tokens: $3 per 1M
- After 200K tokens: $6 per 1M

This incentivizes efficient prompt engineering while allowing large context when needed.

---

## ➡️ Next Phase

Once Phase 1 is complete, proceed to **[PHASE_2_STORAGE.md](./PHASE_2_STORAGE.md)** for storage layer implementation.
