# LLM Pricing API Reference

Complete API documentation for the `llm_pricing` package.

## Table of Contents

1. [Core Classes](#core-classes)
2. [Main API (LLMPricing)](#main-api-llmpricing)
3. [Data Models](#data-models)
4. [Result Objects](#result-objects)
5. [Exceptions](#exceptions)
6. [Convenience Functions](#convenience-functions)

---

## Core Classes

### LLMPricing

Main class for interacting with the LLM pricing database.

```python
from llm_pricing import LLMPricing
from pathlib import Path

# Initialize with default location (project root)
pricing = LLMPricing()

# Initialize with custom location
pricing = LLMPricing(local_path=Path("/custom/path"))
```

#### Methods

##### `calculate(usage, provider, model, tier=None) -> PricingResult`

Calculate the cost for a given token usage.

**Parameters:**
- `usage` (TokenUsage): Token usage details
- `provider` (str): Provider ID (e.g., "openai")
- `model` (str): Model ID (e.g., "gpt-4o")
- `tier` (str, optional): Tier ID. Defaults to "default"

**Returns:** PricingResult object with cost breakdown

**Example:**
```python
from llm_pricing import LLMPricing, TokenUsage

pricing = LLMPricing()
usage = TokenUsage(input_tokens=100000, output_tokens=50000)

result = pricing.calculate(
    provider="openai",
    model="gpt-4o",
    usage=usage,
    tier="default"
)

print(f"Total cost: ${result.total_cost}")
```

##### `list_providers() -> Dict[str, Provider]`

Get all providers in the database.

**Returns:** Dictionary mapping provider IDs to Provider objects

**Example:**
```python
providers = pricing.list_providers()
for provider_id, provider in providers.items():
    print(f"{provider.name}: {len(provider.models)} models")
```

##### `list_models(provider=None) -> List[ModelInfo]`

Get all models, optionally filtered by provider.

**Parameters:**
- `provider` (str, optional): Filter by provider ID

**Returns:** List of ModelInfo objects

**Example:**
```python
# All models
all_models = pricing.list_models()

# Models from specific provider
openai_models = pricing.list_models(provider="openai")
for model in openai_models:
    print(f"{model.model_id}: {model.name}")
```

##### `add_provider(provider: Provider) -> None`

Add a new provider to the database.

**Parameters:**
- `provider` (Provider): Provider object to add

**Raises:** ValidationError if provider_id already exists

**Example:**
```python
from llm_pricing import Provider, ProviderTier

provider = Provider(
    provider_id="my-company",
    name="My Company AI",
    tiers={"default": ProviderTier(tier_id="default", name="Default")},
)
pricing.add_provider(provider)
```

##### `add_model(provider_id: str, model: ModelInfo) -> None`

Add a model to a provider.

**Parameters:**
- `provider_id` (str): Provider ID
- `model` (ModelInfo): Model object to add

**Raises:** ValidationError if provider doesn't exist or model_id already exists

**Example:**
```python
from llm_pricing import ModelInfo, ModelPrice
from decimal import Decimal

model = ModelInfo(
    model_id="my-model",
    name="My Model",
    provider_id="my-company",
    pricing=ModelPrice(
        input_mtok=Decimal("1.0"),
        output_mtok=Decimal("2.0"),
    ),
)
pricing.add_model("my-company", model)
```

##### `delete_provider(provider_id: str) -> None`

Delete a provider and all its models.

**Parameters:**
- `provider_id` (str): Provider ID to delete

**Raises:** ValidationError if provider doesn't exist

**Example:**
```python
pricing.delete_provider("my-company")
```

##### `delete_model(provider_id: str, model_id: str) -> None`

Delete a specific model.

**Parameters:**
- `provider_id` (str): Provider ID
- `model_id` (str): Model ID to delete

**Raises:** ValidationError if provider or model doesn't exist

**Example:**
```python
pricing.delete_model("openai", "gpt-4o")
```

##### `store_snapshot() -> SnapshotInfo`

Store the current database state as a snapshot.

**Returns:** SnapshotInfo with snapshot details

**Example:**
```python
snapshot_info = pricing.store_snapshot()
print(f"Saved: {snapshot_info.filename}")
```

##### `validate(provider, model) -> bool`

Validate that a provider and model exist in local storage.

Checks if both the provider and model exist and are available in the current pricing database. Useful for validating user input or external provider/model names before attempting calculations.

**Parameters:**
- `provider` (str): Provider ID (e.g., "anthropic")
- `model` (str): Model ID (e.g., "claude-3-opus-20250219")

**Returns:** 
- `True` if both provider and model exist and are available
- `False` if either provider or model doesn't exist

**Raises:** 
- `ValueError` if provider or model is an empty string

**Example:**
```python
from llm_pricing import LLMPricing, TokenUsage

pricing = LLMPricing()

# Check if provider and model exist
if pricing.validate(provider="anthropic", model="claude-3-opus-20250219"):
    result = pricing.calculate(
        provider="anthropic",
        model="claude-3-opus-20250219",
        usage=TokenUsage(input_tokens=1000, output_tokens=500),
    )
    print(f"Cost: ${result.total_cost}")
else:
    print("Provider or model not found")

# Safe pattern for user input (e.g., from Django form)
provider_id = request.POST.get("provider")
model_id = request.POST.get("model")

if not pricing.validate(provider=provider_id, model=model_id):
    return JsonResponse({
        "error": f"Provider '{provider_id}' or model '{model_id}' not available"
    }, status=400)

# Proceed with calculation
result = pricing.calculate(
    provider=provider_id,
    model=model_id,
    usage=TokenUsage(input_tokens=5000, output_tokens=2000),
)
```

#### Properties

##### `provider_count -> int`

Get the total number of providers.

```python
print(f"Providers: {pricing.provider_count}")
```

##### `model_count -> int`

Get the total number of models across all providers.

```python
print(f"Models: {pricing.model_count}")
```

---

## Data Models

All data models use Pydantic for validation.

### TokenUsage

Token usage for cost calculation.

```python
from llm_pricing import TokenUsage

usage = TokenUsage(
    input_tokens=100000,          # Required
    output_tokens=50000,          # Required
    cache_read_tokens=0,          # Optional (default: 0)
    cache_write_tokens=0,         # Optional (default: 0)
)
```

**Attributes:**
- `input_tokens` (int): Number of input tokens
- `output_tokens` (int): Number of output tokens
- `cache_read_tokens` (int, optional): Cache read tokens (default: 0)
- `cache_write_tokens` (int, optional): Cache write tokens (default: 0)

### Provider

LLM provider (OpenAI, Anthropic, etc.).

```python
from llm_pricing import Provider, ProviderTier, ModelInfo

provider = Provider(
    provider_id="openai",
    name="OpenAI",
    description="OpenAI's GPT models",
    api_endpoint_pattern="https://api.openai.com/v1",
    documentation_url="https://platform.openai.com/docs",
    tiers={
        "free": ProviderTier(tier_id="free", name="Free"),
        "pro": ProviderTier(tier_id="pro", name="Pro"),
    },
    models={
        "gpt-4o": ModelInfo(...)
    },
    is_available=True,
)
```

**Attributes:**
- `provider_id` (str): Unique provider identifier
- `name` (str): Human-readable name
- `description` (str, optional): Provider description
- `api_endpoint_pattern` (str, optional): API URL pattern
- `documentation_url` (str, optional): Pricing documentation URL
- `tiers` (Dict[str, ProviderTier]): Available tiers
- `models` (Dict[str, ModelInfo]): Available models
- `is_available` (bool): Whether provider is active
- `created_at` (datetime): Creation timestamp
- `updated_at` (datetime): Last update timestamp

### ProviderTier

A tier within a provider.

```python
from llm_pricing import ProviderTier

tier = ProviderTier(
    tier_id="pro",
    name="Pro",
    description="Professional tier",
    is_available=True,
)
```

**Attributes:**
- `tier_id` (str): Unique tier identifier
- `name` (str): Human-readable name
- `description` (str, optional): Tier description
- `is_available` (bool): Whether tier is available
- `created_at` (datetime): Creation timestamp
- `updated_at` (datetime): Last update timestamp

### ModelInfo

Model information with pricing and rate limiters.

```python
from llm_pricing import ModelInfo, ModelPrice, ModelRateLimits
from decimal import Decimal

model = ModelInfo(
    model_id="gpt-4o",
    name="GPT-4 Optimized",
    provider_id="openai",
    description="Fast and capable model",
    context_window=131072,
    pricing=ModelPrice(
        input_mtok=Decimal("2.50"),
        output_mtok=Decimal("10.00"),
    ),
    rate_limiters={
        "default": ModelRateLimits(rpm=100, rpd=1000, tpm=4000000),
        "free": ModelRateLimits(rpm=3, rpd=50),
    },
    match_patterns=["gpt-4o", "gpt4o"],
    is_available=True,
    prices_checked="2025-12-01",
)
```

**Attributes:**
- `model_id` (str): Unique model identifier
- `name` (str): Human-readable name
- `provider_id` (str): Parent provider ID
- `description` (str, optional): Model description
- `context_window` (int): Maximum context size in tokens
- `pricing` (ModelPrice): Pricing configuration
- `rate_limiters` (Dict[str, ModelRateLimits]): Rate limits per tier
- `match_patterns` (List[str], optional): Patterns for matching
- `is_available` (bool): Whether model is available
- `prices_checked` (date, optional): Last price check date
- `created_at` (datetime): Creation timestamp
- `updated_at` (datetime): Last update timestamp

**Methods:**
- `get_rate_limits(tier_id: str) -> Optional[ModelRateLimits]`: Get rate limits for a tier

### ModelPrice

Pricing configuration for a model.

```python
from llm_pricing import ModelPrice, TieredPrice, PriceTier
from decimal import Decimal

# Simple pricing
simple = ModelPrice(
    input_mtok=Decimal("2.50"),
    output_mtok=Decimal("10.00"),
    cache_read_mtok=Decimal("0.25"),
    cache_write_mtok=Decimal("2.50"),
)

# Tiered pricing (e.g., Claude Sonnet 4.5)
tiered = ModelPrice(
    input_mtok=TieredPrice(
        base=Decimal("3.00"),
        tiers=[
            PriceTier(start=200000, price=Decimal("6.00")),
        ],
    ),
    output_mtok=Decimal("15.00"),
)
```

**Attributes:**
- `input_mtok` (Union[Decimal, TieredPrice]): Input token price
- `output_mtok` (Union[Decimal, TieredPrice]): Output token price
- `cache_read_mtok` (Optional[Union[Decimal, TieredPrice]]): Cache read price
- `cache_write_mtok` (Optional[Union[Decimal, TieredPrice]]): Cache write price
- `credit_rate_per_mtok` (Optional[Decimal]): Platform credit rate per 1M total tokens (blended); admin-configured, not API-sourced. Must be non-negative; `None` means unconfigured

**Methods:**
- `calculate_input_cost(tokens: int) -> Decimal`: Calculate input cost
- `calculate_output_cost(tokens: int) -> Decimal`: Calculate output cost
- `calculate_cache_read_cost(tokens: int) -> Decimal`: Calculate cache read cost
- `calculate_cache_write_cost(tokens: int) -> Decimal`: Calculate cache write cost

### TieredPrice

Token-count-based tiered pricing.

```python
from llm_pricing import TieredPrice, PriceTier
from decimal import Decimal

tiered = TieredPrice(
    base=Decimal("3.00"),  # $3 per 1M for first 200K tokens
    tiers=[
        PriceTier(start=200000, price=Decimal("6.00")),   # $6 per 1M after 200K
        PriceTier(start=1000000, price=Decimal("4.00")),  # $4 per 1M after 1M
    ],
)

# Calculate cost for 300K tokens
cost = tiered.calculate_cost(300000)
# First 200K: 200,000 × $3 / 1M = $0.60
# Next 100K:  100,000 × $6 / 1M = $0.60
# Total: $1.20
```

**Attributes:**
- `base` (Decimal): Base price per 1M tokens
- `tiers` (List[PriceTier]): Additional tiers (sorted by start)

**Methods:**
- `get_price_at(tokens: int) -> Decimal`: Get price at token count
- `calculate_cost(tokens: int) -> Decimal`: Calculate total cost

### PriceTier

A pricing tier definition.

```python
from llm_pricing import PriceTier
from decimal import Decimal

tier = PriceTier(
    start=200000,              # Token count where tier starts
    price=Decimal("6.00"),     # Price per 1M tokens
)
```

**Attributes:**
- `start` (int): Token count where tier starts
- `price` (Decimal): Price per 1M tokens

### ModelRateLimits

Rate limits for a model on a specific tier.

```python
from llm_pricing import ModelRateLimits

limits = ModelRateLimits(
    rpm=100,           # Requests per minute
    rpd=1000,          # Requests per day
    tpm=4000000,       # Tokens per minute (total)
    tpd=100000000,     # Tokens per day
    itpm=2000000,      # Input tokens per minute
    otpm=2000000,      # Output tokens per minute
)
```

**Attributes:**
- `rpm` (Optional[int]): Requests per minute
- `rpd` (Optional[int]): Requests per day
- `tpm` (Optional[int]): Tokens per minute (total)
- `tpd` (Optional[int]): Tokens per day
- `itpm` (Optional[int]): Input tokens per minute
- `otpm` (Optional[int]): Output tokens per minute

**Note:** At least one limit must be specified.

---

## Result Objects

### PricingResult

Result of a cost calculation.

```python
from llm_pricing import LLMPricing, TokenUsage

pricing = LLMPricing()
result = pricing.calculate(
    provider="openai",
    model="gpt-4o",
    usage=TokenUsage(input_tokens=100000, output_tokens=50000),
)

# Access results
print(result.input_cost)       # Decimal
print(result.output_cost)      # Decimal
print(result.cache_read_cost)  # Decimal (0 if no cache)
print(result.cache_write_cost) # Decimal (0 if no cache)
print(result.subtotal)         # Decimal (all costs without multiplier)
print(result.total_cost)       # Decimal (final cost)
```

**Attributes:**
- `input_cost` (Decimal): Cost for input tokens
- `output_cost` (Decimal): Cost for output tokens
- `cache_read_cost` (Decimal): Cost for cache reads
- `cache_write_cost` (Decimal): Cost for cache writes
- `subtotal` (Decimal): Sum of all costs
- `total_cost` (Decimal): Final cost (same as subtotal for now)

### SnapshotInfo

Information about a stored snapshot.

```python
snapshot_info = pricing.store_snapshot()

print(snapshot_info.filename)        # "2025-12-01_150806_853276.json"
print(snapshot_info.timestamp)       # datetime
print(snapshot_info.provider_count)  # int
print(snapshot_info.model_count)     # int
```

**Attributes:**
- `filename` (str): Snapshot filename
- `timestamp` (datetime): When snapshot was created
- `provider_count` (int): Number of providers in snapshot
- `model_count` (int): Number of models in snapshot

---

## Exceptions

All exceptions inherit from `LLMPricingError`.

### LLMPricingError

Base exception for the package.

```python
from llm_pricing import LLMPricingError

try:
    pricing.calculate(...)
except LLMPricingError as e:
    print(f"Error: {e}")
```

### Common Exceptions

- `ValidationError` (Pydantic): Invalid data or duplicate IDs
- `StorageError`: Problem reading/writing data
- `ValueError`: Invalid arguments to methods

**Example:**
```python
from pydantic import ValidationError

try:
    pricing.add_provider(provider)
except ValidationError as e:
    print(f"Validation failed: {e}")
```

---

## Convenience Functions

### calculate_cost()

Quick cost calculation without creating an instance.

```python
from llm_pricing import calculate_cost, TokenUsage

result = calculate_cost(
    provider="openai",
    model="gpt-4o",
    usage=TokenUsage(input_tokens=100000, output_tokens=50000),
)

print(f"Cost: ${result.total_cost}")
```

**Parameters:**
- `provider` (str): Provider ID
- `model` (str): Model ID
- `usage` (TokenUsage): Token usage
- `tier` (str, optional): Tier ID

**Returns:** PricingResult

---

## Type Aliases

```python
from llm_pricing.models import PriceValue

# PriceValue can be either:
# - Decimal: Simple flat price
# - TieredPrice: Token-count-based tiered pricing

PriceValue = Union[Decimal, TieredPrice]
```

---

## Complete Example

```python
from llm_pricing import (
    LLMPricing, Provider, ProviderTier, ModelInfo, 
    ModelPrice, TokenUsage, calculate_cost
)
from decimal import Decimal
from pathlib import Path

# 1. Initialize
pricing = LLMPricing(local_path=Path("./data"))

# 2. Add provider
provider = Provider(
    provider_id="my-company",
    name="My Company AI",
    tiers={"default": ProviderTier(tier_id="default", name="Default")},
)
pricing.add_provider(provider)

# 3. Add model
model = ModelInfo(
    model_id="my-model",
    name="My Model v1",
    provider_id="my-company",
    pricing=ModelPrice(
        input_mtok=Decimal("1.00"),
        output_mtok=Decimal("2.00"),
    ),
)
pricing.add_model("my-company", model)

# 4. Calculate cost
usage = TokenUsage(input_tokens=10000, output_tokens=5000)
result = pricing.calculate(
    provider="my-company",
    model="my-model",
    usage=usage,
)

print(f"Input:  ${result.input_cost:.4f}")
print(f"Output: ${result.output_cost:.4f}")
print(f"Total:  ${result.total_cost:.4f}")

# 5. Store snapshot for team
snapshot = pricing.store_snapshot()
print(f"Saved: {snapshot.filename}")

# 6. Quick calculation without instance
result2 = calculate_cost(
    provider="my-company",
    model="my-model",
    usage=TokenUsage(input_tokens=50000, output_tokens=25000),
)
print(f"Cost: ${result2.total_cost:.4f}")
```

---

## Performance Notes

- **Auto-loading**: First instantiation automatically loads latest snapshot if data.json doesn't exist
- **Caching**: Models are cached in memory after loading
- **Persistence**: Changes are automatically saved to data.json
- **Snapshots**: Git-tracked for team collaboration

---

## See Also

- [README.md](../README.md) - Quick start and features
- [CLI Usage](CLI.md) - Interactive command-line interface
- [Data Structures](STRUCTURE_UPDATE_SUMMARY.md) - Data model overview
