# LLM Pricing

A standalone Python package for LLM pricing with provider tiers, model-based rate limiters, and tiered pricing support.

## Features

- **Provider Tiers**: Free, Pro, Enterprise, and custom tiers
- **Model-Based Rate Limiters**: Different rate limits per model per tier
- **Tiered Pricing**: Context-based pricing like Claude Sonnet 4.5
- **Local Working Data**: `data.json` at project root (git-ignored, persistent)
- **Snapshots**: Reference snapshots in `data_versions/` folder (git-tracked)
- **Auto-Load**: Automatically loads latest snapshot on first run
- **Simple API**: `calculate`, `list_providers`, `list_models`, `add_provider`, `add_model`, `delete_provider`, `delete_model`, `store_snapshot`

## Storage Architecture

```
project_root/
├── data.json              # Local working data (git-ignored, persistent)
├── data_versions/         # Snapshots (git-tracked, reference only)
│   ├── 2025-12-01_*.json
│   └── ...
└── ...
```

**Key Concepts:**
- **data.json**: Persistent local working data. Modified by user via API. Never committed to git.
- **data_versions/**: Reference snapshots. Created with `store_snapshot()`. Git-tracked for team collaboration.
- **Auto-Load**: On first run, if `data.json` doesn't exist, the latest snapshot is loaded automatically
- **Local Persistence**: Once `data.json` is created, it persists between runs until explicitly deleted

## Installation

### From GitHub (Development)

```bash
# Clone the repository
git clone https://github.com/your-org/llm-pricing.git
cd llm-pricing

# Install in development mode
pip install -e ".[dev]"

# Run tests to verify installation
pytest
```

### From GitHub (Standard Installation)

```bash
# Install directly from GitHub
pip install git+https://github.com/your-org/llm-pricing.git
```

### Local Installation

```bash
# After cloning
pip install -e .
```

## Quick Start

### First Run (Auto-Load from Snapshot)

```python
from llm_pricing import LLMPricing, TokenUsage

# Initialize - auto-loads latest snapshot if available
pricing = LLMPricing()

# Use pricing data that was loaded
result = pricing.calculate(
    provider="openai",
    model="gpt-4o-mini",
    usage=TokenUsage(input_tokens=100000, output_tokens=50000)
)
print(f"Cost: ${result.total_cost}")
```

### Build Custom Data

```python
from llm_pricing import LLMPricing, Provider, ProviderTier, ModelInfo, ModelPrice
from decimal import Decimal

# Initialize
pricing = LLMPricing()

# Add a provider
provider = Provider(
    provider_id="openai",
    name="OpenAI",
    tiers={"default": ProviderTier(tier_id="default", name="Default")},
    models={},
)
pricing.add_provider(provider)

# Add a model
model = ModelInfo(
    model_id="gpt-4o-mini",
    name="GPT-4o Mini",
    provider_id="openai",
    pricing={
        "default": ModelPrice(
            input_mtok=Decimal("0.15"),
            output_mtok=Decimal("0.60"),
        ),
    },
)
pricing.add_model("openai", model)

# Calculate cost
usage = TokenUsage(input_tokens=100000, output_tokens=50000)
result = pricing.calculate(
    provider="openai",
    model="gpt-4o-mini",
    usage=usage,
)

print(f"Input cost:  ${result.input_cost}")
print(f"Output cost: ${result.output_cost}")
print(f"Total cost:  ${result.total_cost}")

# Store as snapshot for team collaboration
snapshot_info = pricing.store_snapshot()
print(f"Snapshot saved: {snapshot_info.filename}")
```

### Cleanup Data

```python
# Delete a specific model
pricing.delete_model("openai", "gpt-4o-mini")

# Delete entire provider
pricing.delete_provider("openai")

# Check updated counts
print(f"Providers: {pricing.provider_count}")
print(f"Models: {pricing.model_count}")
```

### Validate Providers and Models

```python
from llm_pricing import LLMPricing

pricing = LLMPricing()

# Check if provider and model exist before calculating
if pricing.validate(provider="anthropic", model="claude-3-opus-20250219"):
    result = pricing.calculate(
        provider="anthropic",
        model="claude-3-opus-20250219",
        usage=TokenUsage(input_tokens=10000, output_tokens=5000),
    )
    print(f"Cost: ${result.total_cost}")
else:
    print("Provider or model not available")

# Use for input validation (e.g., Django form)
provider_id = request.POST.get("provider")
model_id = request.POST.get("model")

if not pricing.validate(provider=provider_id, model=model_id):
    return JsonResponse({"error": "Invalid provider or model"}, status=400)
```

## Convenience Function

```python
from llm_pricing import calculate_cost, TokenUsage

# Quick cost calculation without managing instance
result = calculate_cost(
    provider="openai",
    model="gpt-4o-mini",
    usage=TokenUsage(input_tokens=50000, output_tokens=25000)
)
print(f"Cost: ${result.total_cost}")
```

## API Reference

### Core Methods

- `calculate(usage, provider, model, tier=None)` - Calculate cost for token usage
- `list_providers()` - Get all providers
- `list_models(provider=None)` - Get models (optionally filtered)
- `add_provider(provider)` - Add a new provider
- `add_model(provider, model)` - Add a model to a provider
- `delete_provider(provider_id)` - Delete a provider and its models
- `delete_model(provider_id, model_id)` - Delete a specific model
- `store_snapshot()` - Save current data as a snapshot

### Properties

- `provider_count` - Number of providers
- `model_count` - Total number of models

## Workflow Example

```python
from llm_pricing import LLMPricing, Provider, ProviderTier, ModelInfo, ModelPrice
from decimal import Decimal

# 1. Initialize (loads latest snapshot automatically)
pricing = LLMPricing()

# 2. Add custom providers and models
custom_provider = Provider(
    provider_id="my-company",
    name="My Company AI",
    tiers={"free": ProviderTier(tier_id="free", name="Free")},
    models={},
)
pricing.add_provider(custom_provider)

# 3. List and view
for provider_id, provider in pricing.list_providers().items():
    print(f"{provider.name}: {len(provider.models)} models")

# 4. Modify as needed
pricing.delete_model("openai", "gpt-4o-mini")  # Remove old model

# 5. Save for team
snapshot_info = pricing.store_snapshot()
print(f"Team snapshot: {snapshot_info.filename}")

# 6. Use for calculations
result = pricing.calculate(
    provider="my-company",
    model="my-model",
    usage=TokenUsage(input_tokens=10000, output_tokens=5000)
)
```

## Git Workflow

```bash
# Clone repo
git clone ...
cd project

# First run - auto-loads latest snapshot
python main.py

# data.json is created automatically from snapshot
# (data.json is git-ignored)

# Make changes, commit snapshot
# ...edits...
python -c "from llm_pricing import LLMPricing; LLMPricing().store_snapshot()"
git add data_versions/
git commit -m "Update pricing snapshots"
```

## Data Formats

### Provider Model

```python
Provider(
    provider_id="openai",
    name="OpenAI",
    tiers={
        "free": ProviderTier(tier_id="free", name="Free"),
        "pro": ProviderTier(tier_id="pro", name="Pro"),
    },
    models={
        "gpt-4o": ModelInfo(...)
    }
)
```

### ModelInfo with Tiered Pricing

```python
from llm_pricing import ModelInfo, ModelPrice, TieredPrice, PriceTier

ModelInfo(
    model_id="claude-sonnet-4",
    name="Claude Sonnet 4",
    provider_id="anthropic",
    pricing={
        "default": TieredPrice(
            base=ModelPrice(input_mtok=Decimal("3"), output_mtok=Decimal("15")),
            tiers=[
                PriceTier(
                    input_threshold=Decimal("1000000"),
                    input_mtok=Decimal("2.5"),
                    output_mtok=Decimal("12.5"),
                ),
            ],
        )
    }
)
```

## Advanced Usage

### Custom Data Paths

```python
from pathlib import Path
from llm_pricing import LLMPricing

# Use custom directory for data.json
pricing = LLMPricing(local_path=Path("/custom/data/path"))
```

### Snapshots

```python
# List available snapshots
snapshots = pricing._snapshot_manager.list_snapshots()
for snapshot in snapshots:
    print(f"{snapshot.filename}: {snapshot.provider_count} providers")

# Store with custom location (if needed)
info = pricing.store_snapshot()
```

## Rate Limiters

Models support model-based rate limiters per tier:

```python
from llm_pricing import ModelRateLimits

limits = ModelRateLimits(
    rpm=100000,      # Requests per minute
    rpd=1000000,     # Requests per day
    tpm=2000000,     # Tokens per minute
    tpd=100000000,   # Tokens per day
    itpm=200000,     # Input tokens per minute
    otpm=200000,     # Output tokens per minute
)
```

# Method 2: Direct token counts
result = calculate_cost(
    provider="openai",
    model="gpt-4o-mini",
    input_tokens=50000,
    output_tokens=25000,
)

print(f"Cost: ${result.total_cost}")
```

## Tiered Pricing (Like Claude Sonnet 4.5)

```python
from llm_pricing import ModelPrice, TieredPrice, PriceTier
from decimal import Decimal

# Model with tiered input pricing
model_price = ModelPrice(
    input_mtok=TieredPrice(
        base=Decimal("3.00"),  # $3 per 1M tokens for first 200K
        tiers=[
            PriceTier(
                start=200000,  # After 200K tokens
                price=Decimal("6.00"),  # $6 per 1M tokens
            ),
        ],
    ),
    output_mtok=Decimal("2.00"),
)

# For 300K input tokens:
# First 200K: 200,000 × $3 / 1M = $0.60
# Next 100K:  100,000 × $6 / 1M = $0.60
# Total: $1.20
```

## Model-Based Rate Limiters

```python
from llm_pricing import ModelRateLimits

# Rate limiters per tier (not provider-based!)
rate_limiters = {
    "free": ModelRateLimits(rpm=10, rpd=100, tpm=1_000_000),
    "pro": ModelRateLimits(rpm=50, rpd=1000, tpm=5_000_000),
    "enterprise": ModelRateLimits(rpm=1000, rpd=10000, tpm=50_000_000),
}

# Add to model
model.rate_limiters = rate_limiters
```

## Data Models

The package uses Pydantic models for type safety:

- `Provider`: API provider (OpenAI, Anthropic, etc.)
- `ProviderTier`: Tier within a provider (Free, Pro, Enterprise)
- `ModelInfo`: Model information with pricing and rate limiters
- `ModelPrice`: Pricing configuration (supports simple and tiered pricing)
- `TieredPrice`: Context-based pricing with multiple tiers
- `ModelRateLimits`: Rate limits for a specific model per tier
- `PricingDatabase`: Root container for all pricing data

## Development

### Project Structure

```
llm-pricing/
├── llm_pricing/              # Main package
│   ├── __init__.py
│   ├── llm_pricing.py        # Main LLMPricing class
│   ├── models.py             # Data models
│   ├── repository.py         # Repository layer
│   ├── snapshot.py           # Snapshot management
│   ├── calculate_cost_function.py
│   ├── constants.py
│   ├── exceptions.py
│   ├── engine/               # Pricing engine
│   │   ├── engine.py
│   │   ├── tiered.py
│   │   ├── cache.py
│   │   └── types.py
│   └── storage/              # Storage layer
│       ├── local_storage.py
│       ├── data_versions.py
│       ├── config.py
│       └── data_versions/    # Bundled snapshots
├── tests/                    # Test suite
│   ├── test_llm_pricing.py
│   ├── test_pricing_engine.py
│   ├── test_repository.py
│   ├── test_snapshot.py
│   └── test_storage.py
├── examples/                 # Example usage
│   └── comprehensive_example.py
├── docs/                     # Documentation
│   ├── API.md
│   ├── DEVELOPMENT.md
│   ├── CONTRIBUTING.md
│   └── plan/
├── scripts/                  # Utility scripts
├── data_versions/            # Snapshots (git-tracked)
├── data.json                 # Working data (git-ignored)
├── README.md
├── CHANGELOG.md
├── LICENSE
└── pyproject.toml
```

### Quick Start for Development

```bash
# Clone the repository
git clone https://github.com/your-org/llm-pricing.git
cd llm-pricing

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage report
pytest --cov=llm_pricing --cov-report=html

# Run the comprehensive example
python examples/comprehensive_example.py

# Format code
black llm_pricing tests

# Lint code
ruff check llm_pricing tests

# Type check
mypy llm_pricing
```

### Run the comprehensive example

```bash
python examples/comprehensive_example.py
```

This demonstrates all major features:
- Basic cost calculation
- Listing providers and models
- Adding custom providers
- Adding custom models
- Tiered pricing
- Convenience functions
- Storing snapshots

### Install development dependencies

```bash
pip install -e ".[dev]"
```

### Run tests

```bash
pytest tests/
```

Tests cover:
- All 6 core API methods
- Pricing engine with flat and tiered rates
- Storage and snapshots
- 137+ test cases with >88% coverage

### Code style

```bash
black llm_pricing tests
ruff check llm_pricing tests
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- How to report bugs
- How to suggest features
- Development workflow
- Pull request process

## Support & Documentation

- **API Documentation**: See [docs/API.md](docs/API.md) for complete API reference
- **Development Guide**: See [DEVELOPMENT.md](DEVELOPMENT.md) for setup and contribution details
- **Examples**: Check [examples/](examples/) for comprehensive usage examples
- **Issues**: Open an issue on GitHub for bugs or feature requests

## Status

**Latest Version**: 0.1.0 (Alpha)

| Component | Status |
|-----------|--------|
| Core API | ✅ Complete |
| Storage Layer | ✅ Complete |
| Pricing Engine | ✅ Complete |
| Snapshot Management | ✅ Complete |
| Tests | ✅ 137+ tests passing |
| Documentation | ✅ Complete |

See [docs/plan/PROGRESS_CHECKLIST.md](docs/plan/PROGRESS_CHECKLIST.md) for detailed implementation progress.

## License

MIT - See [LICENSE](LICENSE) for details
