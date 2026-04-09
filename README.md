# llm-pricing

Standalone Python package for LLM pricing with provider tiers, model-based rate limiters, and tiered pricing support.

## Installation

```bash
pip install llm-pricing
# or with uv
uv add llm-pricing
```

## Quick Start

```python
from llm_pricing import LLMPricing, TokenUsage

# Initialize - auto-loads latest pricing data
pricing = LLMPricing()

# Calculate cost
result = pricing.calculate(
    provider="openai",
    model="gpt-4o-mini",
    usage=TokenUsage(input_tokens=100000, output_tokens=50000),
)
print(f"Cost: ${result.total_cost}")
```

## Features

- **Provider Tiers**: Free, Pro, Enterprise, and custom tiers
- **Model-Based Rate Limiters**: Different rate limits per model per tier
- **Tiered Pricing**: Context-based pricing (e.g., Claude Sonnet 4.5)
- **Snapshot Management**: Versioned pricing data snapshots for team collaboration
- **Local Working Data**: Automatic load from latest snapshot, persisted locally

## API Overview

### Core Methods

| Method | Description |
|--------|-------------|
| `calculate(provider, model, usage)` | Calculate cost for token usage |
| `list_providers()` | Get all providers |
| `list_models(provider=None)` | Get models, optionally filtered |
| `add_provider(provider)` | Add a new provider |
| `add_model(provider, model)` | Add a model to a provider |
| `delete_provider(provider_id)` | Delete a provider and its models |
| `delete_model(provider_id, model_id)` | Delete a specific model |
| `store_snapshot()` | Save current data as a snapshot |
| `validate(provider, model)` | Check if provider/model exists |

### Convenience Function

```python
from llm_pricing import calculate_cost, TokenUsage

result = calculate_cost(
    provider="openai",
    model="gpt-4o-mini",
    usage=TokenUsage(input_tokens=50000, output_tokens=25000),
)
```

### Tiered Pricing

```python
from llm_pricing import ModelPrice, TieredPrice, PriceTier
from decimal import Decimal

model_price = ModelPrice(
    input_mtok=TieredPrice(
        base=Decimal("3.00"),
        tiers=[PriceTier(start=200000, price=Decimal("6.00"))],
    ),
    output_mtok=Decimal("2.00"),
)
```

### Rate Limiters

```python
from llm_pricing import ModelRateLimits

rate_limiters = {
    "free": ModelRateLimits(rpm=10, rpd=100, tpm=1_000_000),
    "pro": ModelRateLimits(rpm=50, rpd=1000, tpm=5_000_000),
}
```

## Configuration

- **Local data path**: Defaults to project root. Override with `LLMPricing(local_path=Path("/custom"))` 
- **Data format**: All data is JSON, managed by Pydantic models
- **Snapshots**: Stored in `data_versions/` directory, git-tracked

## Testing

```bash
uv sync --all-groups --all-extras
uv run pytest -m "not integration and not e2e" -q   # PR gate
uv run pytest -q                                       # full local
```

## License

MIT
