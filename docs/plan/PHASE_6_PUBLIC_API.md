# Phase 6: Public API

## Overview

This phase implements the public-facing Python API for the `llm-pricing` package. The API provides a simple, unified interface through the `LLMPricing` class with only the essential methods users need.

**Note: No CLI is implemented.** This is a library-only package.

## Goals

- Provide a clean, simple Python API
- Single entry point through `LLMPricing` class
- Only essential methods: `calculate`, `list_providers`, `list_models`, `add_provider`, `add_model`, `store_snapshot`
- Easy to use with sensible defaults
- Clear error messages

## Public API Methods

| Method | Description |
|--------|-------------|
| `calculate(usage, provider, model, tier)` | Calculate cost for token usage |
| `list_providers()` | Get all providers with their data |
| `list_models(provider_id)` | Get all models, optionally filtered |
| `add_provider(provider)` | Add a new provider |
| `add_model(provider_id, model)` | Add a new model to a provider |
| `store_snapshot()` | Save current data as a bundled snapshot |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Application                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      LLMPricing                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  calculate()  list_providers()  list_models()           ││
│  │  add_provider()  add_model()  store_snapshot()          ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
┌───────────────────┐ ┌─────────────┐ ┌─────────────────────┐
│ PricingRepository │ │   Engine    │ │  SnapshotManager    │
└───────────────────┘ └─────────────┘ └─────────────────────┘
            │                 │                 │
            └─────────────────┼─────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Storage Layer                            │
│          LocalStorage + DataVersionManager                   │
└─────────────────────────────────────────────────────────────┘
```

## Implementation

### 6.1 Main LLMPricing Class

```python
# src/llm_pricing/__init__.py
"""LLM Pricing Package - Calculate LLM API costs with tiered pricing support."""

from pathlib import Path
from typing import Optional
from decimal import Decimal

from .models import (
    Provider,
    ModelInfo,
    ModelPrice,
    TieredPrice,
    PriceTier,
    PricingDatabase,
)
from .storage import LocalStorage, DataVersionManager
from .repository import PricingRepository, create_repository
from .engine import PricingEngine, TokenUsage, CostBreakdown
from .snapshot import SnapshotManager, SnapshotInfo

__version__ = "0.1.0"

# Re-export commonly used types
__all__ = [
    "LLMPricing",
    "TokenUsage",
    "CostBreakdown",
    "Provider",
    "ModelInfo",
    "ModelPrice",
    "TieredPrice",
    "PriceTier",
    "SnapshotInfo",
]


class LLMPricing:
    """Main interface for LLM pricing operations.
    
    This class provides a simple API for:
    - Calculating costs for API usage
    - Listing providers and models
    - Adding custom providers and models
    - Storing snapshots
    
    Data is automatically loaded from bundled snapshots on first use,
    then stored locally at ~/.llm_pricing/data.json.
    
    Example:
        ```python
        from llm_pricing import LLMPricing, TokenUsage
        
        # Initialize
        pricing = LLMPricing()
        
        # Calculate cost
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        result = pricing.calculate(
            usage=usage,
            provider='anthropic',
            model='claude-sonnet-4-20250514',
        )
        print(f"Total cost: ${result.total_cost}")
        
        # List providers
        providers = pricing.list_providers()
        for p_id, provider in providers.items():
            print(f"{p_id}: {provider.name}")
        ```
    """
    
    def __init__(
        self,
        local_path: Optional[Path] = None,
    ):
        """Initialize LLMPricing.
        
        Args:
            local_path: Custom path for local data storage.
                       Defaults to ~/.llm_pricing/data.json
        
        Data is automatically loaded from:
        1. Local storage (if exists)
        2. Latest bundled snapshot (if no local data)
        3. Empty database (if no snapshots available)
        """
        # Initialize storage and repository
        self._local_storage = LocalStorage(path=local_path)
        self._version_manager = DataVersionManager()
        self._repo = PricingRepository(
            self._local_storage,
            self._version_manager,
        )
        
        # Initialize engine and snapshot manager
        self._engine = PricingEngine(self._repo)
        self._snapshot_manager = SnapshotManager(
            self._repo,
            self._version_manager,
        )
    
    # === Core API Methods ===
    
    def calculate(
        self,
        usage: TokenUsage,
        provider: str,
        model: str,
        tier: Optional[str] = None,
    ) -> CostBreakdown:
        """Calculate cost for token usage.
        
        Args:
            usage: TokenUsage with input, output, and cache tokens
            provider: Provider ID (e.g., 'anthropic', 'openai')
            model: Model ID (e.g., 'claude-sonnet-4-20250514', 'gpt-4o')
            tier: Optional provider tier for pricing multipliers
        
        Returns:
            CostBreakdown with detailed cost information
            
        Raises:
            ValueError: If provider/model not found or has no pricing
        
        Example:
            ```python
            usage = TokenUsage(
                input_tokens=100000,
                output_tokens=50000,
                cache_read_tokens=20000,
            )
            result = pricing.calculate(
                usage=usage,
                provider='anthropic',
                model='claude-sonnet-4-5-20250514',
            )
            
            print(f"Input cost: ${result.input_cost}")
            print(f"Output cost: ${result.output_cost}")
            print(f"Cache read cost: ${result.cache_read_cost}")
            print(f"Total: ${result.total_cost}")
            
            # View tiered breakdown
            for tier in result.input_breakdown:
                print(f"  {tier.tokens} tokens @ ${tier.price_per_million}/M")
            ```
        """
        return self._engine.calculate(
            provider_id=provider,
            model_id=model,
            usage=usage,
            tier=tier,
        )
    
    def list_providers(self) -> dict[str, Provider]:
        """Get all providers with their complete data.
        
        Returns:
            Dictionary mapping provider ID to Provider object.
            Each Provider contains its models, tiers, and metadata.
        
        Example:
            ```python
            providers = pricing.list_providers()
            
            for provider_id, provider in providers.items():
                print(f"{provider_id}: {provider.name}")
                print(f"  Models: {len(provider.models)}")
                if provider.tiers:
                    print(f"  Tiers: {list(provider.tiers.keys())}")
            ```
        """
        return self._repo.list_providers()
    
    def list_models(
        self,
        provider_id: Optional[str] = None,
    ) -> list[ModelInfo]:
        """Get all models, optionally filtered by provider.
        
        Args:
            provider_id: Optional provider ID to filter by
        
        Returns:
            List of ModelInfo objects
        
        Example:
            ```python
            # All models
            all_models = pricing.list_models()
            print(f"Total models: {len(all_models)}")
            
            # Models for specific provider
            anthropic_models = pricing.list_models(provider_id='anthropic')
            for model in anthropic_models:
                print(f"{model.id}: {model.name}")
                if model.price:
                    print(f"  Input: ${model.price.input.base}/M")
                    print(f"  Output: ${model.price.output.base}/M")
            ```
        """
        return self._repo.list_models(provider_id=provider_id)
    
    def add_provider(self, provider: Provider) -> Provider:
        """Add a new provider.
        
        The provider is saved immediately to local storage.
        
        Args:
            provider: Provider object to add
        
        Returns:
            The added provider
        
        Raises:
            ValueError: If provider with same ID already exists
        
        Example:
            ```python
            from llm_pricing import Provider
            
            provider = Provider(
                id='my-company',
                name='My Company',
                models={},
            )
            pricing.add_provider(provider)
            ```
        """
        return self._repo.add_provider(provider)
    
    def add_model(
        self,
        provider_id: str,
        model: ModelInfo,
    ) -> ModelInfo:
        """Add a new model to a provider.
        
        The model is saved immediately to local storage.
        
        Args:
            provider_id: Provider ID to add model to
            model: ModelInfo object to add
        
        Returns:
            The added model
        
        Raises:
            ValueError: If provider doesn't exist or model already exists
        
        Example:
            ```python
            from decimal import Decimal
            from llm_pricing import ModelInfo, ModelPrice, TieredPrice
            
            model = ModelInfo(
                id='my-model-v1',
                name='My Model V1',
                price=ModelPrice(
                    input=TieredPrice(base=Decimal('1.0')),
                    output=TieredPrice(base=Decimal('5.0')),
                ),
            )
            pricing.add_model('my-company', model)
            ```
        """
        return self._repo.add_model(provider_id, model)
    
    def store_snapshot(self) -> SnapshotInfo:
        """Store current data as a new bundled snapshot.
        
        Creates a new snapshot file in the package's data_versions folder
        with the current local data. The snapshot uses datetime-based naming.
        
        This is useful for persisting custom pricing data that should be
        bundled with the package for distribution.
        
        Returns:
            SnapshotInfo with details about the created snapshot
        
        Example:
            ```python
            # Add custom data
            pricing.add_provider(Provider(...))
            pricing.add_model('my-provider', ModelInfo(...))
            
            # Store as snapshot
            info = pricing.store_snapshot()
            print(f"Created: {info.filename}")
            print(f"Providers: {info.provider_count}")
            print(f"Models: {info.model_count}")
            ```
        """
        return self._snapshot_manager.create_snapshot()
    
    # === Convenience Properties ===
    
    @property
    def provider_count(self) -> int:
        """Number of providers in the database."""
        return len(self._repo.list_providers())
    
    @property
    def model_count(self) -> int:
        """Total number of models across all providers."""
        return len(self._repo.list_models())


# Convenience function for quick calculations
def calculate_cost(
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    tier: Optional[str] = None,
) -> CostBreakdown:
    """Convenience function for quick cost calculations.
    
    Creates a temporary LLMPricing instance for one-off calculations.
    For multiple calculations, create an LLMPricing instance instead.
    
    Args:
        provider: Provider ID
        model: Model ID
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cache_read_tokens: Tokens read from cache
        cache_creation_tokens: Tokens used to create cache
        tier: Optional provider tier
    
    Returns:
        CostBreakdown with cost information
    
    Example:
        ```python
        from llm_pricing import calculate_cost
        
        result = calculate_cost(
            provider='anthropic',
            model='claude-sonnet-4-20250514',
            input_tokens=1000,
            output_tokens=500,
        )
        print(f"Cost: ${result.total_cost}")
        ```
    """
    pricing = LLMPricing()
    usage = TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_creation_tokens=cache_creation_tokens,
    )
    return pricing.calculate(
        usage=usage,
        provider=provider,
        model=model,
        tier=tier,
    )
```

### 6.2 Package Re-exports

```python
# src/llm_pricing/__init__.py (exports section)

# Main class
from .llm_pricing import LLMPricing, calculate_cost

# Types for users
from .engine import TokenUsage, CostBreakdown, TierBreakdown
from .models import (
    Provider,
    ModelInfo,
    ModelPrice,
    TieredPrice,
    PriceTier,
    ProviderTier,
    ModelRateLimits,
    TierRateLimiters,
    RateLimiterType,
    RateLimitValue,
)
from .snapshot import SnapshotInfo

__all__ = [
    # Main API
    "LLMPricing",
    "calculate_cost",
    
    # Usage/Result types
    "TokenUsage",
    "CostBreakdown",
    "TierBreakdown",
    "SnapshotInfo",
    
    # Model types (for add_provider/add_model)
    "Provider",
    "ModelInfo",
    "ModelPrice",
    "TieredPrice",
    "PriceTier",
    "ProviderTier",
    "ModelRateLimits",
    "TierRateLimiters",
    "RateLimiterType",
    "RateLimitValue",
]
```

## File Structure After Phase 6

```
src/llm_pricing/
├── __init__.py            # Package exports and LLMPricing class
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
├── engine/
│   ├── __init__.py
│   ├── types.py
│   ├── tiered.py
│   ├── cache.py
│   └── engine.py
└── snapshot.py
```

## Usage Examples

### Basic Usage

```python
from llm_pricing import LLMPricing, TokenUsage

# Initialize
pricing = LLMPricing()

# Calculate cost
usage = TokenUsage(
    input_tokens=100000,
    output_tokens=50000,
)
result = pricing.calculate(
    usage=usage,
    provider='anthropic',
    model='claude-sonnet-4-20250514',
)

print(f"Input cost: ${result.input_cost}")
print(f"Output cost: ${result.output_cost}")
print(f"Total cost: ${result.total_cost}")
```

### Quick Calculation

```python
from llm_pricing import calculate_cost

# One-liner for quick calculations
result = calculate_cost(
    provider='openai',
    model='gpt-4o',
    input_tokens=5000,
    output_tokens=2000,
)
print(f"Cost: ${result.total_cost}")
```

### Exploring Available Models

```python
from llm_pricing import LLMPricing

pricing = LLMPricing()

# List all providers
providers = pricing.list_providers()
print(f"Available providers: {len(providers)}")
for p_id, provider in providers.items():
    print(f"  {p_id}: {provider.name} ({len(provider.models)} models)")

# List models for a provider
models = pricing.list_models(provider_id='anthropic')
for model in models:
    print(f"{model.id}")
    if model.price:
        print(f"  Input: ${model.price.input.base}/M tokens")
        print(f"  Output: ${model.price.output.base}/M tokens")
```

### Adding Custom Pricing Data

```python
from decimal import Decimal
from llm_pricing import (
    LLMPricing,
    Provider,
    ModelInfo,
    ModelPrice,
    TieredPrice,
    PriceTier,
)

pricing = LLMPricing()

# Add a custom provider
provider = Provider(
    id='my-company',
    name='My Company LLM',
    models={},
)
pricing.add_provider(provider)

# Add a model with tiered pricing
model = ModelInfo(
    id='my-model-v1',
    name='My Model V1',
    price=ModelPrice(
        input=TieredPrice(
            base=Decimal('2.0'),
            tiers=[
                PriceTier(range_start=100000, range_end=None, price=Decimal('4.0')),
            ],
        ),
        output=TieredPrice(base=Decimal('10.0')),
    ),
)
pricing.add_model('my-company', model)

# Store as snapshot for future use
info = pricing.store_snapshot()
print(f"Saved snapshot: {info.filename}")
```

### Tiered Pricing Calculation

```python
from llm_pricing import LLMPricing, TokenUsage

pricing = LLMPricing()

# Calculate with usage that crosses tier thresholds
usage = TokenUsage(
    input_tokens=300000,  # Crosses 200K threshold for Claude Sonnet 4.5
    output_tokens=100000,
)

result = pricing.calculate(
    usage=usage,
    provider='anthropic',
    model='claude-sonnet-4-5-20250514',
)

# View tier breakdown
print("Input cost breakdown:")
for tier in result.input_breakdown:
    print(f"  {tier.tier_start}-{tier.tier_end or '∞'}: "
          f"{tier.tokens} tokens @ ${tier.price_per_million}/M = ${tier.cost}")

print(f"\nTotal input: ${result.input_cost}")
print(f"Total output: ${result.output_cost}")
print(f"Grand total: ${result.total_cost}")
```

## Test Cases

### Unit Tests

```python
# tests/test_llm_pricing.py
import pytest
from decimal import Decimal
from pathlib import Path
import tempfile

from llm_pricing import (
    LLMPricing,
    TokenUsage,
    CostBreakdown,
    Provider,
    ModelInfo,
    ModelPrice,
    TieredPrice,
    calculate_cost,
)


class TestLLMPricing:
    """Tests for main LLMPricing class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def pricing_with_data(self, temp_dir):
        """Create LLMPricing with sample data."""
        # Set up with bundled snapshot
        versions_dir = temp_dir / "llm_pricing" / "data_versions"
        versions_dir.mkdir(parents=True)
        
        # Create sample snapshot
        from llm_pricing.models import PricingDatabase
        data = PricingDatabase(
            version="1.0.0",
            providers={
                "test-provider": Provider(
                    id="test-provider",
                    name="Test Provider",
                    models={
                        "test-model": ModelInfo(
                            id="test-model",
                            name="Test Model",
                            price=ModelPrice(
                                input=TieredPrice(base=Decimal("3.0")),
                                output=TieredPrice(base=Decimal("15.0")),
                            ),
                        ),
                    },
                ),
            },
        )
        snapshot_path = versions_dir / "2025-01-15_120000.json"
        snapshot_path.write_text(data.model_dump_json())
        
        local_path = temp_dir / "local" / "data.json"
        return LLMPricing(local_path=local_path)
    
    # === Test calculate ===
    
    def test_calculate_basic(self, pricing_with_data):
        """Test basic cost calculation."""
        usage = TokenUsage(input_tokens=1000000, output_tokens=500000)
        
        result = pricing_with_data.calculate(
            usage=usage,
            provider="test-provider",
            model="test-model",
        )
        
        assert result.input_cost == Decimal("3.0")   # 1M at $3/M
        assert result.output_cost == Decimal("7.5")  # 0.5M at $15/M
        assert result.total_cost == Decimal("10.5")
    
    def test_calculate_model_not_found(self, pricing_with_data):
        """Test error when model not found."""
        usage = TokenUsage(input_tokens=1000)
        
        with pytest.raises(ValueError, match="not found"):
            pricing_with_data.calculate(
                usage=usage,
                provider="test-provider",
                model="nonexistent",
            )
    
    def test_calculate_provider_not_found(self, pricing_with_data):
        """Test error when provider not found."""
        usage = TokenUsage(input_tokens=1000)
        
        with pytest.raises(ValueError, match="not found"):
            pricing_with_data.calculate(
                usage=usage,
                provider="unknown",
                model="test-model",
            )
    
    # === Test list_providers ===
    
    def test_list_providers(self, pricing_with_data):
        """Test listing providers."""
        providers = pricing_with_data.list_providers()
        
        assert "test-provider" in providers
        assert providers["test-provider"].name == "Test Provider"
    
    # === Test list_models ===
    
    def test_list_models_all(self, pricing_with_data):
        """Test listing all models."""
        models = pricing_with_data.list_models()
        
        assert len(models) == 1
        assert models[0].id == "test-model"
    
    def test_list_models_by_provider(self, pricing_with_data):
        """Test listing models by provider."""
        models = pricing_with_data.list_models(provider_id="test-provider")
        
        assert len(models) == 1
        assert models[0].id == "test-model"
    
    def test_list_models_unknown_provider(self, pricing_with_data):
        """Test listing models for unknown provider."""
        models = pricing_with_data.list_models(provider_id="unknown")
        
        assert models == []
    
    # === Test add_provider ===
    
    def test_add_provider(self, pricing_with_data):
        """Test adding a provider."""
        provider = Provider(
            id="new-provider",
            name="New Provider",
            models={},
        )
        
        result = pricing_with_data.add_provider(provider)
        
        assert result.id == "new-provider"
        assert "new-provider" in pricing_with_data.list_providers()
    
    def test_add_provider_duplicate(self, pricing_with_data):
        """Test adding duplicate provider raises error."""
        provider = Provider(
            id="test-provider",  # Already exists
            name="Duplicate",
            models={},
        )
        
        with pytest.raises(ValueError, match="already exists"):
            pricing_with_data.add_provider(provider)
    
    # === Test add_model ===
    
    def test_add_model(self, pricing_with_data):
        """Test adding a model."""
        model = ModelInfo(
            id="new-model",
            name="New Model",
            price=ModelPrice(
                input=TieredPrice(base=Decimal("1.0")),
                output=TieredPrice(base=Decimal("5.0")),
            ),
        )
        
        result = pricing_with_data.add_model("test-provider", model)
        
        assert result.id == "new-model"
        models = pricing_with_data.list_models(provider_id="test-provider")
        assert len(models) == 2
    
    def test_add_model_unknown_provider(self, pricing_with_data):
        """Test adding model to unknown provider."""
        model = ModelInfo(
            id="test",
            name="Test",
            price=ModelPrice(
                input=TieredPrice(base=Decimal("1.0")),
                output=TieredPrice(base=Decimal("1.0")),
            ),
        )
        
        with pytest.raises(ValueError, match="not found"):
            pricing_with_data.add_model("unknown", model)
    
    # === Test store_snapshot ===
    
    def test_store_snapshot(self, pricing_with_data):
        """Test storing a snapshot."""
        info = pricing_with_data.store_snapshot()
        
        assert info.filename.endswith(".json")
        assert info.provider_count == 1
        assert info.model_count == 1
        assert info.path.exists()
    
    # === Test properties ===
    
    def test_provider_count(self, pricing_with_data):
        """Test provider_count property."""
        assert pricing_with_data.provider_count == 1
    
    def test_model_count(self, pricing_with_data):
        """Test model_count property."""
        assert pricing_with_data.model_count == 1


class TestCalculateCostFunction:
    """Tests for calculate_cost convenience function."""
    
    def test_calculate_cost_basic(self, monkeypatch, tmp_path):
        """Test convenience function."""
        # This would use real data or mocked LLMPricing
        # For unit test, we'd mock the LLMPricing class
        pass  # Integration test with real data


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""
    
    def test_defaults(self):
        """Test default values."""
        usage = TokenUsage()
        
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cache_read_tokens == 0
        assert usage.cache_creation_tokens == 0
    
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
```

## Dependencies

### Phase Dependencies

- **Phase 1** (Data Models): All model types
- **Phase 2** (Storage): LocalStorage, DataVersionManager
- **Phase 3** (Repository): PricingRepository
- **Phase 4** (Engine): PricingEngine, TokenUsage, CostBreakdown
- **Phase 5** (Snapshot): SnapshotManager, SnapshotInfo

### Python Dependencies

No additional dependencies. Uses only:
- Standard library (`pathlib`, `decimal`, `typing`)
- Internal modules

## Acceptance Criteria

- [ ] `LLMPricing` class implemented with all 6 methods
- [ ] `calculate()` returns correct `CostBreakdown`
- [ ] `list_providers()` returns all providers
- [ ] `list_models()` returns models with optional filtering
- [ ] `add_provider()` adds and persists new provider
- [ ] `add_model()` adds and persists new model
- [ ] `store_snapshot()` creates valid snapshot file
- [ ] `calculate_cost()` convenience function works
- [ ] All types properly exported from package
- [ ] Clear error messages for invalid operations
- [ ] All unit tests passing
- [ ] Integration tests with real data passing

## Notes

### Design Decisions

1. **No CLI**: This is a library-only package. Users integrate via Python API.

2. **Simple Method Signatures**: Methods use clear, typed parameters rather than complex options objects.

3. **Immediate Persistence**: Changes from `add_provider()` and `add_model()` are saved immediately.

4. **Convenience Function**: `calculate_cost()` provides a quick one-liner for simple use cases.

5. **Type Re-exports**: Common types are re-exported from the main package for easy imports.

### Error Handling

All methods raise `ValueError` with descriptive messages for:
- Provider not found
- Model not found
- Duplicate provider/model
- Missing pricing data

### Thread Safety

The current implementation is **not thread-safe**. For concurrent usage, create separate `LLMPricing` instances or implement external synchronization.
