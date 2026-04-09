# Development Guide

## Prerequisites

- Python >= 3.10
- uv

## Setup

```bash
uv sync --all-groups --all-extras
```

## Unit Tests (PR Gate)

Run unit tests only (no external dependencies):

```bash
uv run pytest -m "not integration and not e2e" -q
```

## Integration / E2E Tests

Run all tests:

```bash
uv run pytest -q
```

Run specific test types:

```bash
uv run pytest -m integration
uv run pytest -m e2e
```

## Coverage

```bash
uv run pytest -m "not integration and not e2e" --cov --cov-report=term-missing
```

## CI Behavior

The CI workflow runs the PR-gated unit tests on every push and pull request. Tests are configured with markers:
- `@pytest.mark.unit` — no external dependencies (PR-gated)
- `@pytest.mark.integration` — requires storage layer (not PR-gated)
- `@pytest.mark.e2e` — full system flow (not PR-gated)

## Known Issues

- None currently

## Code Quality Tools

```bash
# Format
black llm_pricing tests

# Lint
ruff check llm_pricing tests --fix

# Type check
mypy llm_pricing
```

## Project Structure

```
llm_pricing/
├── __init__.py              # Public API exports
├── llm_pricing.py           # Main LLMPricing class
├── models.py                # Pydantic data models
├── repository.py            # Data access layer
├── snapshot.py              # Snapshot management
├── calculate_cost_function.py
├── constants.py
├── exceptions.py
├── engine/                  # Pricing calculation
│   ├── engine.py
│   ├── tiered.py
│   ├── cache.py
│   └── types.py
└── storage/                 # Data persistence
    ├── config.py
    ├── local_storage.py
    └── data_versions.py

tests/
├── conftest.py              # Shared fixtures
├── test_llm_pricing.py      # Main API tests
├── test_pricing_engine.py   # Calculation engine tests
├── test_repository.py       # Repository layer tests
├── test_snapshot.py         # Snapshot tests
└── test_storage.py          # Storage layer tests

examples/
└── comprehensive_example.py

docs/
├── API.md                   # Full API reference
└── development.md           # This file
```

## Adding Tests

1. Place test files in `tests/` directory
2. Name them `test_*.py`
3. Add appropriate marker: `@pytest.mark.unit`, `@pytest.mark.integration`, or `@pytest.mark.e2e`
4. Use fixtures from `conftest.py` when applicable

## Debugging

```bash
# Run specific test with output
uv run pytest tests/test_llm_pricing.py::TestCalculateMethod::test_calculate_basic -v -s

# Run with pdb
uv run pytest --pdb tests/test_llm_pricing.py
```
