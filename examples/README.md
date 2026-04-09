# Examples

This directory contains example code demonstrating the `llm-pricing` package usage.

## Available Examples

### `comprehensive_example.py`

Demonstrates all major features:
- Basic cost calculation
- Listing providers and models
- Adding custom providers
- Adding custom models
- Tiered pricing
- Convenience functions
- Storing snapshots

## Running Examples

```bash
# From the repository root
python examples/comprehensive_example.py

# Or using uv
uv run python examples/comprehensive_example.py
```

## Prerequisites

Install the package in development mode:

```bash
uv sync --all-groups --all-extras
# or
pip install -e ".[dev]"
```

## Expected Output

Each example prints results to stdout. You should see:
- Provider and model listings
- Cost calculations
- Snapshot confirmation

## Creating New Examples

When adding new examples:
1. Name them descriptively (e.g., `tiered_pricing_example.py`)
2. Add clear comments explaining each step
3. Include expected output in comments
4. Update this README
