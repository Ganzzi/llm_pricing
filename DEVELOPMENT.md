# Development Guide

Complete guide for setting up the development environment and working with the llm-pricing codebase.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Environment Setup](#environment-setup)
3. [Architecture Overview](#architecture-overview)
4. [Running Tests](#running-tests)
5. [Code Quality Tools](#code-quality-tools)
6. [Debugging](#debugging)
7. [Common Tasks](#common-tasks)

## Quick Start

```bash
# Clone the repository
git clone https://github.com/your-org/llm-pricing.git
cd llm-pricing

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# You're ready to develop!
```

## Environment Setup

### Prerequisites

- Python 3.9+
- pip or poetry
- Git

### Python Version Check

```bash
python --version
# Should be 3.9 or higher
```

### Virtual Environment

**Using venv (recommended):**

```bash
# Create
python -m venv venv

# Activate
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows PowerShell
. venv/Scripts/Activate   # Windows cmd
```

**Using poetry (alternative):**

```bash
pip install poetry
poetry install --with dev
poetry shell
```

### Install Dependencies

**Development installation** (editable + dev tools):

```bash
pip install -e ".[dev]"
```

**Production installation**:

```bash
pip install -e .
```

**Manual installation** (if needed):

```bash
pip install pydantic>=2.0
pip install pytest>=7.0 pytest-cov>=4.0 black>=23.0 ruff>=0.1 mypy>=1.0
```

## Architecture Overview

### Package Structure

```
llm_pricing/
├── __init__.py                  # Package exports
├── llm_pricing.py              # Main LLMPricing class (public API)
├── models.py                   # Data models (Pydantic)
├── repository.py               # Repository layer (data access)
├── snapshot.py                 # Snapshot management
├── calculate_cost_function.py  # Convenience functions
├── constants.py                # Constants and enums
├── exceptions.py               # Custom exceptions
│
├── engine/                     # Pricing calculation engine
│   ├── __init__.py
│   ├── types.py               # TokenUsage, CostBreakdown
│   ├── engine.py              # PricingEngine class
│   ├── tiered.py              # Tiered pricing calculation
│   └── cache.py               # Cache pricing calculation
│
└── storage/                    # Data storage layer
    ├── __init__.py
    ├── config.py              # StorageConfig
    ├── local_storage.py       # LocalStorage (file I/O)
    ├── data_versions.py       # DataVersionManager (snapshots)
    └── data_versions/         # Bundled snapshots
        └── *.json
```

### Layer Architecture

```
┌─────────────────────────────────────┐
│    LLMPricing (Public API)          │ ← User interface
├─────────────────────────────────────┤
│    PricingRepository                │ ← Data access
├─────────────────────────────────────┤
│    LocalStorage, DataVersionManager │ ← Storage layer
├─────────────────────────────────────┤
│    File System (data.json)          │ ← Persistence
└─────────────────────────────────────┘
```

### Data Flow

```
calculate(provider, model, usage, tier)
    ↓
LLMPricing.calculate()
    ↓
PricingEngine.calculate()
    ↓
ModelPrice methods (flat or tiered pricing)
    ↓
PricingResult (with cost breakdown)
```

## Running Tests

### Basic Test Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_llm_pricing.py

# Run specific test
pytest tests/test_llm_pricing.py::test_calculate_cost

# Run with verbose output
pytest -v

# Run with markers
pytest -m "not slow"
```

### Coverage Reports

```bash
# Terminal report
pytest --cov=llm_pricing --cov-report=term-missing

# HTML report (opens in browser)
pytest --cov=llm_pricing --cov-report=html
open htmlcov/index.html  # macOS/Linux
start htmlcov\index.html # Windows
```

### Test Organization

```
tests/
├── conftest.py              # Fixtures and configuration
├── test_llm_pricing.py      # LLMPricing class tests
├── test_pricing_engine.py   # PricingEngine tests
├── test_repository.py       # Repository tests
├── test_snapshot.py         # Snapshot manager tests
└── test_storage.py          # Storage layer tests
```

### Common Test Patterns

**Using fixtures:**

```python
def test_with_pricing_instance(pricing_instance):
    """Test using pricing fixture from conftest.py"""
    result = pricing_instance.calculate(...)
    assert result.total_cost > 0
```

**Testing exceptions:**

```python
import pytest

def test_raises_on_invalid_provider():
    """Test that ValueError is raised for invalid input"""
    with pytest.raises(ValueError, match="provider"):
        pricing.calculate(...)
```

**Parameterized tests:**

```python
@pytest.mark.parametrize("tokens,expected", [
    (100000, Decimal("0.30")),
    (1000000, Decimal("3.00")),
])
def test_calculate_with_various_tokens(tokens, expected):
    """Test calculate with multiple inputs"""
    cost = calculate_tiered_cost(tokens, Decimal("3.00"))
    assert cost == expected
```

## Code Quality Tools

### Black (Code Formatting)

```bash
# Format all files
black llm_pricing tests

# Format specific file
black llm_pricing/llm_pricing.py

# Check without changing
black --check llm_pricing tests
```

### Ruff (Linting)

```bash
# Check all files
ruff check llm_pricing tests

# Fix issues automatically
ruff check llm_pricing tests --fix

# Check specific rule
ruff check llm_pricing --select=E501  # line too long
```

### MyPy (Type Checking)

```bash
# Check all files
mypy llm_pricing

# Ignore missing imports if needed
mypy llm_pricing --ignore-missing-imports
```

### Running All Quality Checks

```bash
# Format
black llm_pricing tests

# Lint
ruff check llm_pricing tests --fix

# Type check
mypy llm_pricing

# Test
pytest

# Coverage
pytest --cov=llm_pricing --cov-report=term-missing
```

**Or use a script:**

```bash
#!/bin/bash
set -e
echo "Formatting..."
black llm_pricing tests
echo "Linting..."
ruff check llm_pricing tests --fix
echo "Type checking..."
mypy llm_pricing
echo "Testing..."
pytest --cov=llm_pricing
echo "✓ All checks passed!"
```

## Debugging

### Print Debugging

```python
from llm_pricing import LLMPricing
import json

pricing = LLMPricing()

# Debug print current state
print(json.dumps(pricing.list_providers(), indent=2, default=str))

# Use logging
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("Debug message")
```

### Using Python Debugger

```python
# Add breakpoint
from llm_pricing import LLMPricing

pricing = LLMPricing()
breakpoint()  # Execution pauses here
result = pricing.calculate(...)  # Step through with debugger
```

**In VS Code:**
- Set breakpoint by clicking line number
- Press F5 to run debugger
- Use Debug Console to inspect variables

### Testing Specific Scenarios

```bash
# Test with specific Python version
python3.9 -m pytest tests/
python3.10 -m pytest tests/
python3.11 -m pytest tests/
python3.12 -m pytest tests/

# Test specific feature
pytest tests/ -k "tiered"

# Test with print output
pytest tests/ -s
```

## Common Tasks

### Adding a New Feature

1. **Create tests first**
   ```bash
   # tests/test_new_feature.py
   def test_new_functionality():
       # Arrange
       # Act
       # Assert
   ```

2. **Run tests to see them fail**
   ```bash
   pytest tests/test_new_feature.py
   ```

3. **Implement the feature**
   ```python
   # llm_pricing/new_module.py
   def new_function():
       """Implementation with docstring"""
   ```

4. **Run tests to see them pass**
   ```bash
   pytest
   ```

5. **Check code quality**
   ```bash
   black llm_pricing tests
   ruff check llm_pricing tests --fix
   mypy llm_pricing
   ```

### Updating Data Models

When modifying Pydantic models in `models.py`:

```python
from pydantic import BaseModel, Field
from decimal import Decimal

class NewModel(BaseModel):
    """Clear docstring explaining the model"""
    
    field1: str = Field(..., description="Field description")
    field2: Decimal = Field(gt=0, description="Must be positive")
    
    model_config = ConfigDict(
        frozen=False,  # Or True for immutable
        json_schema_extra={"example": {...}}
    )
```

**Then:**
1. Update tests in `test_*.py`
2. Update JSON serialization if needed
3. Update documentation

### Handling Storage Changes

If changing data format:

1. Update `storage/local_storage.py` if file I/O changes
2. Create new snapshot in `data_versions/` with updated format
3. Update `DataVersionManager` if needed
4. Add migration path for old data
5. Update tests

### Adding Rate Limiters

To support new rate limiter types:

1. Update `ModelRateLimits` in `models.py`
2. Add validation rules
3. Update `constants.py` if adding enums
4. Add tests
5. Update API documentation

## Project Statistics

```bash
# Count lines of code
cloc llm_pricing

# List all test files
find tests -name "test_*.py"

# Check code complexity
radon cc llm_pricing -a

# Check code metrics
radon metrics llm_pricing
```

## IDE Setup

### VS Code

**Extensions:**
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Black Formatter (ms-python.black-formatter)
- isort (ms-python.isort)

**Settings (.vscode/settings.json):**
```json
{
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": false,
    "python.formatting.provider": "black",
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.organizeImports": "explicit"
        }
    }
}
```

### PyCharm

- Create run configuration for pytest
- Enable code inspections
- Set code style to Black
- Configure test runner to pytest

## Troubleshooting

### Import Errors

```bash
# Ensure package is installed in editable mode
pip install -e .

# Reinstall if issues persist
pip uninstall llm_pricing
pip install -e ".[dev]"
```

### Test Failures

```bash
# Run with verbose output
pytest -vv tests/test_file.py

# Run with print statements
pytest -s tests/test_file.py

# Run with debugging
pytest --pdb tests/test_file.py
```

### Virtual Environment Issues

```bash
# Remove and recreate
rm -rf venv  # Windows: rmdir /s venv
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

## Resources

- **Pydantic**: https://docs.pydantic.dev/
- **Pytest**: https://docs.pytest.org/
- **Black**: https://black.readthedocs.io/
- **Ruff**: https://github.com/astral-sh/ruff
- **MyPy**: https://mypy.readthedocs.io/

## Next Steps

- Read [CONTRIBUTING.md](CONTRIBUTING.md) for contribution workflow
- Check [docs/API.md](docs/API.md) for API reference
- Review [docs/plan/](docs/plan/) for architecture details
- Run the [examples/comprehensive_example.py](examples/comprehensive_example.py)
