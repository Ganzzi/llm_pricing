# Phase 4: Pricing Engine

## Overview

The Pricing Engine calculates costs based on token usage, supporting both flat-rate and tiered pricing structures. This phase implements the core calculation logic for the `calculate()` method, including support for Claude Sonnet 4.5's tiered pricing structure.

## Goals

- Calculate costs for input, output, and cache tokens
- Support flat-rate pricing (single price per million tokens)
- Support tiered pricing (price varies by usage volume)
- Handle provider tier multipliers
- Provide detailed cost breakdowns

## Tiered Pricing Reference

From the original `genai-prices` project, tiered pricing is structured as:

```yaml
# Example: Claude Sonnet 4.5 from anthropic.yml
claude-sonnet-4-5-20250514:
  mode: chat
  input:
    - range: [0, 200000]       # 0-200K tokens
      price: 3                  # $3 per million
    - range: [200000, null]     # 200K+ tokens  
      price: 6                  # $6 per million
  output:
    - range: [0, 200000]
      price: 15
    - range: [200000, null]
      price: 30
  cache_read: 0.3
  cache_creation: 3.75
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     LLMPricing.calculate()                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Pricing Engine                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │  Flat Pricing   │  │  Tiered Pricing │  │   Cache     │  │
│  │   Calculator    │  │   Calculator    │  │ Calculator  │  │
│  └─────────────────┘  └─────────────────┘  └─────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                     Cost Aggregator                          │
│                   (creates CostBreakdown)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   PricingRepository                          │
│                   (provides model data)                      │
└─────────────────────────────────────────────────────────────┘
```

## Implementation

### 4.1 Usage and Result Types

```python
# src/llm_pricing/engine/types.py
"""Types for pricing calculations."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class TokenUsage:
    """Token usage for a single request."""
    
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
            self.input_tokens + 
            self.output_tokens + 
            self.cache_read_tokens + 
            self.cache_creation_tokens
        )


@dataclass
class TierBreakdown:
    """Cost breakdown for a single pricing tier."""
    
    tier_start: int
    tier_end: Optional[int]  # None = unlimited
    price_per_million: Decimal
    tokens: int
    cost: Decimal


@dataclass
class CostBreakdown:
    """Detailed cost breakdown for a usage calculation."""
    
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
        return (
            self.input_cost + 
            self.output_cost + 
            self.cache_read_cost + 
            self.cache_creation_cost
        )
    
    @property
    def total_cost(self) -> Decimal:
        """Total cost with tier multiplier applied."""
        return self.subtotal * self.tier_multiplier
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
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
                    "tier_start": t.tier_start,
                    "tier_end": t.tier_end,
                    "price_per_million": str(t.price_per_million),
                    "tokens": t.tokens,
                    "cost": str(t.cost),
                }
                for t in self.input_breakdown
            ] if self.input_breakdown else None,
            "output_breakdown": [
                {
                    "tier_start": t.tier_start,
                    "tier_end": t.tier_end,
                    "price_per_million": str(t.price_per_million),
                    "tokens": t.tokens,
                    "cost": str(t.cost),
                }
                for t in self.output_breakdown
            ] if self.output_breakdown else None,
        }
```

### 4.2 Tiered Pricing Calculator

```python
# src/llm_pricing/engine/tiered.py
"""Tiered pricing calculator."""
from decimal import Decimal
from typing import Optional

from ..models import TieredPrice, PriceTier
from .types import TierBreakdown


def calculate_tiered_cost(
    tokens: int,
    tiered_price: TieredPrice,
    cumulative_tokens: int = 0,
) -> tuple[Decimal, list[TierBreakdown]]:
    """Calculate cost using tiered pricing.
    
    Args:
        tokens: Number of tokens in this request
        tiered_price: TieredPrice with base rate and optional tiers
        cumulative_tokens: Previously consumed tokens for tier tracking
    
    Returns:
        Tuple of (total_cost, breakdown_list)
        
    Example:
        For Claude Sonnet 4.5 with tiers:
        - 0-200K: $3/M (base)
        - 200K+: $6/M
        
        If cumulative=150K and tokens=100K:
        - First 50K at $3/M = $0.15
        - Remaining 50K at $6/M = $0.30
        - Total = $0.45
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
    
    for tier in all_tiers:
        if remaining_tokens <= 0:
            break
        
        # Skip tiers we've already passed
        if tier.range_end is not None and current_position >= tier.range_end:
            continue
        
        # Determine how many tokens fall in this tier
        tier_start = max(tier.range_start, current_position)
        
        if tier.range_end is None:
            # Unlimited tier - all remaining tokens go here
            tokens_in_tier = remaining_tokens
        else:
            # Limited tier
            space_in_tier = tier.range_end - tier_start
            tokens_in_tier = min(remaining_tokens, space_in_tier)
        
        if tokens_in_tier > 0:
            tier_cost = _flat_cost(tokens_in_tier, tier.price)
            total_cost += tier_cost
            
            breakdown.append(
                TierBreakdown(
                    tier_start=tier.range_start,
                    tier_end=tier.range_end,
                    price_per_million=tier.price,
                    tokens=tokens_in_tier,
                    cost=tier_cost,
                )
            )
            
            remaining_tokens -= tokens_in_tier
            current_position += tokens_in_tier
    
    return total_cost, breakdown


def _flat_cost(tokens: int, price_per_million: Decimal) -> Decimal:
    """Calculate flat-rate cost for tokens."""
    return (Decimal(tokens) / Decimal("1000000")) * price_per_million


def _build_tier_list(tiered_price: TieredPrice) -> list[PriceTier]:
    """Build complete sorted tier list including implicit base tier.
    
    The base price applies from 0 to the first tier threshold.
    """
    tiers = list(tiered_price.tiers)
    
    # If no tier starts at 0, create implicit base tier
    has_zero_tier = any(t.range_start == 0 for t in tiers)
    if not has_zero_tier:
        # Find the lowest tier start to set as base tier end
        min_start = min((t.range_start for t in tiers), default=None)
        base_tier = PriceTier(
            range_start=0,
            range_end=min_start,
            price=tiered_price.base,
        )
        tiers.insert(0, base_tier)
    
    # Sort by range_start
    return sorted(tiers, key=lambda t: t.range_start)
```

### 4.3 Cache Cost Calculator

```python
# src/llm_pricing/engine/cache.py
"""Cache cost calculator."""
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
        cache_creation_tokens: Tokens used to create cache
        cache_read_price: Price per million for cache reads
        cache_creation_price: Price per million for cache creation
    
    Returns:
        Tuple of (cache_read_cost, cache_creation_cost)
    """
    cache_read_cost = Decimal("0")
    cache_creation_cost = Decimal("0")
    
    if cache_read_price is not None and cache_read_tokens > 0:
        cache_read_cost = (
            Decimal(cache_read_tokens) / Decimal("1000000")
        ) * cache_read_price
    
    if cache_creation_price is not None and cache_creation_tokens > 0:
        cache_creation_cost = (
            Decimal(cache_creation_tokens) / Decimal("1000000")
        ) * cache_creation_price
    
    return cache_read_cost, cache_creation_cost
```

### 4.4 Main Pricing Engine

```python
# src/llm_pricing/engine/engine.py
"""Main pricing engine."""
from decimal import Decimal
from typing import Optional

from ..models import ModelInfo, ModelPrice, TieredPrice, Provider
from ..repository import PricingRepository
from .types import TokenUsage, CostBreakdown
from .tiered import calculate_tiered_cost
from .cache import calculate_cache_cost


class PricingEngine:
    """Engine for calculating LLM costs.
    
    Supports:
    - Flat-rate pricing
    - Tiered pricing (Claude Sonnet 4.5 style)
    - Cache read/creation costs
    - Provider tier multipliers
    """
    
    def __init__(self, repository: PricingRepository):
        """Initialize pricing engine.
        
        Args:
            repository: Repository for accessing pricing data
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
        
        Args:
            provider_id: Provider ID (e.g., 'anthropic')
            model_id: Model ID (e.g., 'claude-sonnet-4-20250514')
            usage: Token usage for this request
            tier: Optional provider tier for pricing multipliers
        
        Returns:
            CostBreakdown with detailed pricing information
            
        Raises:
            ValueError: If provider/model not found or has no pricing
            
        Example:
            >>> engine = PricingEngine(repository)
            >>> usage = TokenUsage(
            ...     input_tokens=100000,
            ...     output_tokens=50000,
            ... )
            >>> result = engine.calculate('anthropic', 'claude-sonnet-4-20250514', usage)
            >>> print(f"Total cost: ${result.total_cost}")
        """
        # Get model pricing data
        model = self._repo.get_model(provider_id, model_id)
        if model is None:
            raise ValueError(
                f"Model '{model_id}' not found for provider '{provider_id}'"
            )
        
        if model.price is None:
            raise ValueError(f"No pricing information for model '{model_id}'")
        
        price = model.price
        
        # Calculate input cost
        input_cost, input_breakdown = self._calculate_token_cost(
            tokens=usage.input_tokens,
            pricing=price.input,
        )
        
        # Calculate output cost
        output_cost, output_breakdown = self._calculate_token_cost(
            tokens=usage.output_tokens,
            pricing=price.output,
        )
        
        # Calculate cache costs (always flat-rate)
        cache_read_cost, cache_creation_cost = calculate_cache_cost(
            cache_read_tokens=usage.cache_read_tokens,
            cache_creation_tokens=usage.cache_creation_tokens,
            cache_read_price=price.cache_read,
            cache_creation_price=price.cache_creation,
        )
        
        # Get tier multiplier if applicable
        tier_multiplier = Decimal("1.0")
        tier_name = tier
        if tier:
            provider = self._repo.get_provider(provider_id)
            if provider and provider.tiers:
                tier_info = provider.tiers.get(tier)
                if tier_info and tier_info.multiplier:
                    tier_multiplier = tier_info.multiplier
        
        return CostBreakdown(
            input_cost=input_cost,
            output_cost=output_cost,
            cache_read_cost=cache_read_cost,
            cache_creation_cost=cache_creation_cost,
            input_breakdown=input_breakdown,
            output_breakdown=output_breakdown,
            tier_multiplier=tier_multiplier,
            tier_name=tier_name,
        )
    
    def _calculate_token_cost(
        self,
        tokens: int,
        pricing: Optional[TieredPrice],
    ) -> tuple[Decimal, list]:
        """Calculate cost for tokens using flat or tiered pricing.
        
        Args:
            tokens: Number of tokens
            pricing: TieredPrice (with base rate and optional tiers)
        
        Returns:
            Tuple of (cost, breakdown)
        """
        if pricing is None or tokens == 0:
            return Decimal("0"), []
        
        return calculate_tiered_cost(
            tokens=tokens,
            tiered_price=pricing,
            cumulative_tokens=0,  # We don't track cumulative in simplified API
        )
```

### 4.5 Package Exports

```python
# src/llm_pricing/engine/__init__.py
"""Pricing engine module."""
from .types import TokenUsage, TierBreakdown, CostBreakdown
from .engine import PricingEngine
from .tiered import calculate_tiered_cost
from .cache import calculate_cache_cost

__all__ = [
    "TokenUsage",
    "TierBreakdown",
    "CostBreakdown",
    "PricingEngine",
    "calculate_tiered_cost",
    "calculate_cache_cost",
]
```

## File Structure After Phase 4

```
src/llm_pricing/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── base.py
│   ├── pricing.py
│   ├── rate_limits.py
│   └── database.py
├── storage/
│   ├── __init__.py
│   ├── local.py
│   └── versions.py
├── repository.py
└── engine/                 # NEW
    ├── __init__.py
    ├── types.py
    ├── tiered.py
    ├── cache.py
    └── engine.py
```

## Usage Examples

### Basic Calculation

```python
from llm_pricing import create_repository
from llm_pricing.engine import PricingEngine, TokenUsage

# Create repository and engine
repo = create_repository()
engine = PricingEngine(repo)

# Calculate cost for token usage
usage = TokenUsage(
    input_tokens=100000,
    output_tokens=50000,
)

result = engine.calculate(
    provider_id='anthropic',
    model_id='claude-sonnet-4-20250514',
    usage=usage,
)

print(f"Input cost: ${result.input_cost}")
print(f"Output cost: ${result.output_cost}")
print(f"Total cost: ${result.total_cost}")
```

### Calculation with Cache Tokens

```python
from llm_pricing.engine import TokenUsage

usage = TokenUsage(
    input_tokens=50000,
    output_tokens=20000,
    cache_read_tokens=30000,    # Read from cache
    cache_creation_tokens=10000, # Created cache
)

result = engine.calculate('anthropic', 'claude-sonnet-4-20250514', usage)

print(f"Cache read cost: ${result.cache_read_cost}")
print(f"Cache creation cost: ${result.cache_creation_cost}")
print(f"Total: ${result.total_cost}")
```

### Calculation with Provider Tier

```python
# Calculate with a specific pricing tier
result = engine.calculate(
    provider_id='anthropic',
    model_id='claude-sonnet-4-20250514',
    usage=usage,
    tier='scale',  # Use 'scale' tier pricing
)

print(f"Tier multiplier: {result.tier_multiplier}")
print(f"Total with tier: ${result.total_cost}")
```

### Viewing Tiered Pricing Breakdown

```python
# For models with tiered pricing (like Claude Sonnet 4.5)
usage = TokenUsage(
    input_tokens=300000,  # Crosses 200K threshold
    output_tokens=100000,
)

result = engine.calculate('anthropic', 'claude-sonnet-4-5-20250514', usage)

print("Input breakdown:")
for tier in result.input_breakdown:
    print(f"  {tier.tier_start}-{tier.tier_end or '∞'}: "
          f"{tier.tokens} tokens @ ${tier.price_per_million}/M = ${tier.cost}")
```

## Test Cases

### Unit Tests

```python
# tests/test_pricing_engine.py
import pytest
from decimal import Decimal

from llm_pricing.models import (
    PricingDatabase,
    Provider,
    ModelInfo,
    ModelPrice,
    TieredPrice,
    PriceTier,
)
from llm_pricing.engine import (
    PricingEngine,
    TokenUsage,
    CostBreakdown,
    calculate_tiered_cost,
)


class TestTieredCostCalculation:
    """Tests for tiered pricing calculations."""
    
    def test_flat_rate_no_tiers(self):
        """Test flat rate when no tiers defined."""
        price = TieredPrice(base=Decimal("3.0"))
        
        cost, breakdown = calculate_tiered_cost(
            tokens=1000000,
            tiered_price=price,
        )
        
        assert cost == Decimal("3.0")
        assert len(breakdown) == 1
        assert breakdown[0].tokens == 1000000
    
    def test_single_tier_under_threshold(self):
        """Test usage under first tier threshold."""
        price = TieredPrice(
            base=Decimal("3.0"),
            tiers=[
                PriceTier(range_start=200000, range_end=None, price=Decimal("6.0")),
            ],
        )
        
        cost, breakdown = calculate_tiered_cost(
            tokens=100000,  # Under 200K threshold
            tiered_price=price,
        )
        
        # Should use base price only
        assert cost == Decimal("0.3")  # 100K * $3/M
        assert len(breakdown) == 1
        assert breakdown[0].price_per_million == Decimal("3.0")
    
    def test_single_tier_crosses_threshold(self):
        """Test usage that crosses tier threshold."""
        price = TieredPrice(
            base=Decimal("3.0"),
            tiers=[
                PriceTier(range_start=200000, range_end=None, price=Decimal("6.0")),
            ],
        )
        
        cost, breakdown = calculate_tiered_cost(
            tokens=300000,  # 200K at base, 100K at higher tier
            tiered_price=price,
        )
        
        # 200K at $3/M = $0.60
        # 100K at $6/M = $0.60
        # Total = $1.20
        assert cost == Decimal("1.2")
        assert len(breakdown) == 2
    
    def test_multiple_tiers(self):
        """Test pricing with multiple tiers."""
        price = TieredPrice(
            base=Decimal("3.0"),
            tiers=[
                PriceTier(range_start=100000, range_end=200000, price=Decimal("4.0")),
                PriceTier(range_start=200000, range_end=None, price=Decimal("6.0")),
            ],
        )
        
        cost, breakdown = calculate_tiered_cost(
            tokens=250000,  # 100K at base, 100K at tier1, 50K at tier2
            tiered_price=price,
        )
        
        # 100K at $3/M = $0.30
        # 100K at $4/M = $0.40
        # 50K at $6/M = $0.30
        # Total = $1.00
        assert cost == Decimal("1.0")
        assert len(breakdown) == 3
    
    def test_zero_tokens(self):
        """Test with zero tokens."""
        price = TieredPrice(base=Decimal("3.0"))
        
        cost, breakdown = calculate_tiered_cost(
            tokens=0,
            tiered_price=price,
        )
        
        assert cost == Decimal("0")
        assert breakdown == []


class TestPricingEngine:
    """Tests for the main pricing engine."""
    
    @pytest.fixture
    def sample_database(self) -> PricingDatabase:
        """Create sample database with various pricing models."""
        return PricingDatabase(
            version="1.0.0",
            providers={
                "anthropic": Provider(
                    id="anthropic",
                    name="Anthropic",
                    models={
                        "claude-3-opus": ModelInfo(
                            id="claude-3-opus",
                            name="Claude 3 Opus",
                            price=ModelPrice(
                                input=TieredPrice(base=Decimal("15.0")),
                                output=TieredPrice(base=Decimal("75.0")),
                            ),
                        ),
                        "claude-sonnet-4-5": ModelInfo(
                            id="claude-sonnet-4-5",
                            name="Claude Sonnet 4.5",
                            price=ModelPrice(
                                input=TieredPrice(
                                    base=Decimal("3.0"),
                                    tiers=[
                                        PriceTier(
                                            range_start=200000,
                                            range_end=None,
                                            price=Decimal("6.0"),
                                        ),
                                    ],
                                ),
                                output=TieredPrice(
                                    base=Decimal("15.0"),
                                    tiers=[
                                        PriceTier(
                                            range_start=200000,
                                            range_end=None,
                                            price=Decimal("30.0"),
                                        ),
                                    ],
                                ),
                                cache_read=Decimal("0.3"),
                                cache_creation=Decimal("3.75"),
                            ),
                        ),
                    },
                ),
            },
        )
    
    @pytest.fixture
    def engine(self, sample_database, tmp_path):
        """Create pricing engine with sample data."""
        from llm_pricing.storage import LocalStorage, DataVersionManager
        from llm_pricing.repository import PricingRepository
        
        # Save sample data to local storage
        local_path = tmp_path / "data.json"
        local_path.write_text(sample_database.model_dump_json())
        
        local_storage = LocalStorage(path=local_path)
        version_manager = DataVersionManager(versions_dir=tmp_path / "versions")
        repo = PricingRepository(local_storage, version_manager)
        
        return PricingEngine(repo)
    
    def test_calculate_flat_rate(self, engine):
        """Test calculation with flat rate pricing."""
        usage = TokenUsage(input_tokens=1000000, output_tokens=500000)
        
        result = engine.calculate("anthropic", "claude-3-opus", usage)
        
        assert result.input_cost == Decimal("15.0")   # 1M at $15/M
        assert result.output_cost == Decimal("37.5")  # 0.5M at $75/M
        assert result.total_cost == Decimal("52.5")
    
    def test_calculate_tiered_rate(self, engine):
        """Test calculation with tiered pricing."""
        usage = TokenUsage(input_tokens=300000, output_tokens=100000)
        
        result = engine.calculate("anthropic", "claude-sonnet-4-5", usage)
        
        # Input: 200K at $3/M + 100K at $6/M = $0.60 + $0.60 = $1.20
        assert result.input_cost == Decimal("1.2")
        
        # Output: 100K at $15/M = $1.50
        assert result.output_cost == Decimal("1.5")
    
    def test_calculate_with_cache(self, engine):
        """Test calculation including cache tokens."""
        usage = TokenUsage(
            input_tokens=100000,
            output_tokens=50000,
            cache_read_tokens=50000,
            cache_creation_tokens=20000,
        )
        
        result = engine.calculate("anthropic", "claude-sonnet-4-5", usage)
        
        # Cache read: 50K at $0.3/M = $0.015
        assert result.cache_read_cost == Decimal("0.015")
        
        # Cache creation: 20K at $3.75/M = $0.075
        assert result.cache_creation_cost == Decimal("0.075")
    
    def test_calculate_model_not_found(self, engine):
        """Test error when model not found."""
        usage = TokenUsage(input_tokens=1000)
        
        with pytest.raises(ValueError, match="not found"):
            engine.calculate("anthropic", "nonexistent", usage)
    
    def test_calculate_provider_not_found(self, engine):
        """Test error when provider not found."""
        usage = TokenUsage(input_tokens=1000)
        
        with pytest.raises(ValueError, match="not found"):
            engine.calculate("unknown", "some-model", usage)
    
    def test_cost_breakdown_to_dict(self, engine):
        """Test CostBreakdown serialization."""
        usage = TokenUsage(input_tokens=300000, output_tokens=100000)
        result = engine.calculate("anthropic", "claude-sonnet-4-5", usage)
        
        data = result.to_dict()
        
        assert "input_cost" in data
        assert "output_cost" in data
        assert "total_cost" in data
        assert "input_breakdown" in data


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""
    
    def test_total_tokens(self):
        """Test total_tokens property."""
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150
    
    def test_total_with_cache(self):
        """Test total_with_cache property."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=30,
            cache_creation_tokens=20,
        )
        assert usage.total_with_cache == 200
    
    def test_defaults(self):
        """Test default values."""
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cache_read_tokens == 0
        assert usage.cache_creation_tokens == 0
```

## Dependencies

### Phase Dependencies

- **Phase 1** (Data Models): Uses `ModelInfo`, `ModelPrice`, `TieredPrice`, `PriceTier`
- **Phase 3** (Repository): Uses `PricingRepository` to retrieve model data

### Python Dependencies

No additional dependencies - uses only standard library `decimal` and `dataclasses`.

## Acceptance Criteria

- [ ] `TokenUsage` dataclass implemented with all properties
- [ ] `CostBreakdown` dataclass implemented with serialization
- [ ] `calculate_tiered_cost()` handles flat and tiered pricing correctly
- [ ] `calculate_cache_cost()` handles cache token pricing
- [ ] `PricingEngine.calculate()` produces correct results
- [ ] Tiered pricing breakdown shows correct token distribution
- [ ] Cache costs calculated correctly
- [ ] Provider tier multipliers applied correctly
- [ ] Proper error handling for missing models/providers
- [ ] All unit tests passing

## Notes

### Design Decisions

1. **Decimal for Money**: All costs use `Decimal` to avoid floating-point precision issues.

2. **Stateless Engine**: The engine doesn't track cumulative usage between calls. Each calculation is independent. This simplifies the API and matches our use case.

3. **Breakdown Information**: The `CostBreakdown` includes detailed tier breakdowns for transparency, useful for debugging and understanding costs.

4. **Implicit Base Tier**: The `TieredPrice.base` serves as the price for the implicit 0-to-first-threshold tier, matching genai-prices structure.

## Next Phase

Phase 5 (Data Manager) will coordinate the repository, storage, and engine into the unified `LLMPricing` API class.
