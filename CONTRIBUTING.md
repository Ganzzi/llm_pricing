# Contributing to llm-pricing

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

Be respectful, inclusive, and professional. We're here to build great software together.

## Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub
# Clone your fork
git clone https://github.com/YOUR-USERNAME/llm-pricing.git
cd llm-pricing

# Add upstream remote
git remote add upstream https://github.com/original-org/llm-pricing.git
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev]"

# Verify setup
pytest
```

### 3. Create Feature Branch

```bash
# Update main branch
git fetch upstream
git checkout main
git merge upstream/main

# Create feature branch
git checkout -b feature/your-feature-name
# or for bug fixes:
git checkout -b fix/your-bug-fix
```

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_llm_pricing.py

# Run with coverage
pytest --cov=llm_pricing --cov-report=term-missing

# Run specific test
pytest tests/test_llm_pricing.py::test_calculate_cost
```

### Code Style

We use Black for formatting and Ruff for linting:

```bash
# Format code
black llm_pricing tests

# Run linter
ruff check llm_pricing tests --fix

# Type checking
mypy llm_pricing
```

### Making Changes

1. **Create tests first** (TDD approach recommended)
   ```python
   # tests/test_your_feature.py
   def test_new_functionality():
       # Your test here
       pass
   ```

2. **Implement the feature**
   - Follow existing code style
   - Use Decimal for prices, not float
   - Add type hints
   - Add docstrings

3. **Run tests locally**
   ```bash
   pytest
   pytest --cov=llm_pricing
   ```

4. **Format and lint**
   ```bash
   black llm_pricing tests
   ruff check llm_pricing tests --fix
   mypy llm_pricing
   ```

## Pull Request Process

### Before Submitting

1. **Ensure tests pass**
   ```bash
   pytest --cov=llm_pricing
   ```

2. **Format your code**
   ```bash
   black llm_pricing tests
   ruff check llm_pricing tests --fix
   ```

3. **Update documentation** if needed
   - Update docstrings
   - Update relevant docs in `docs/`
   - Update `CHANGELOG.md`

4. **Rebase on main**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

### Pull Request Title and Description

**Title Format:**
- `feat: Add support for new pricing model`
- `fix: Handle edge case in tiered pricing`
- `docs: Update API documentation`
- `refactor: Simplify pricing engine`
- `test: Add tests for cache pricing`

**Description Should Include:**
- What problem does this solve?
- What changes were made?
- How can reviewers test this?
- Any breaking changes?
- Closes #issue-number (if applicable)

**Example:**
```markdown
## Description
Adds support for volume-based pricing discounts.

## Changes
- Added `VolumeDiscount` model
- Updated `ModelPrice` to support discounts
- Added tests for discount calculations

## How to Test
```python
from llm_pricing import ModelPrice, VolumeDiscount
# Test code here
```

Closes #123
```

### Review Process

- Maintainers will review your PR
- Address feedback and update your branch
- Keep the conversation professional and constructive

## Types of Contributions

### Bug Reports

**Before opening an issue:**
- Check if the issue already exists
- Try to reproduce it
- Gather version info and error messages

**Include in bug report:**
- Description of the bug
- Steps to reproduce
- Expected behavior
- Actual behavior
- Python version, OS
- Error traceback

**Example:**
```markdown
### Bug: calculate() returns incorrect cost

**Python Version:** 3.9
**OS:** Windows 10

**Steps to reproduce:**
1. Create ModelPrice with tiered pricing
2. Call calculate() with 250K tokens
3. See incorrect cost

**Expected:** $1.20
**Actual:** $1.50
```

### Feature Requests

**Include:**
- Clear description of the feature
- Use cases
- Example code showing usage
- Why this feature is useful

**Example:**
```markdown
### Feature: Add batch calculation

**Use Case:** Calculate costs for multiple models at once

**Example:**
```python
results = pricing.calculate_batch([
    (TokenUsage(...), "openai", "gpt-4"),
    (TokenUsage(...), "anthropic", "claude-3"),
])
```
```

### Documentation Improvements

- Typos and unclear explanations
- Missing API documentation
- Examples that could be clearer
- Missing edge case documentation

## Code Guidelines

### Style

- Follow PEP 8
- Max line length: 100 characters
- Use type hints
- Use Decimal for prices (never float)
- Add docstrings to all public functions/classes

### Example Function

```python
def calculate_tiered_cost(
    tokens: int,
    base_price: Decimal,
    tiers: Optional[List[PriceTier]] = None,
) -> Decimal:
    """
    Calculate cost for tokens with optional tiered pricing.
    
    Args:
        tokens: Number of tokens
        base_price: Price per 1M tokens for base tier
        tiers: Optional list of additional tiers
        
    Returns:
        Total cost as Decimal
        
    Example:
        >>> cost = calculate_tiered_cost(
        ...     tokens=300000,
        ...     base_price=Decimal("3.00"),
        ...     tiers=[PriceTier(start=200000, price=Decimal("6.00"))]
        ... )
        >>> cost
        Decimal('1.20')
    """
    # Implementation
```

### Testing Guidelines

- Test happy path and edge cases
- Test error conditions
- Use fixtures for common test data
- Aim for >90% code coverage
- Name tests clearly: `test_calculate_cost_with_tiered_pricing`

```python
def test_calculate_cost_with_tiered_pricing():
    """Test calculate_cost returns correct result for tiered pricing."""
    # Arrange
    tokens = 300000
    base_price = Decimal("3.00")
    tiers = [PriceTier(start=200000, price=Decimal("6.00"))]
    
    # Act
    cost = calculate_tiered_cost(tokens, base_price, tiers)
    
    # Assert
    assert cost == Decimal("1.20")


def test_calculate_cost_raises_on_negative_tokens():
    """Test calculate_cost raises ValueError for negative tokens."""
    with pytest.raises(ValueError):
        calculate_tiered_cost(-100, Decimal("3.00"))
```

## Documentation

### Where to Update

- `README.md` - User-facing overview
- `docs/API.md` - API reference
- `CHANGELOG.md` - Version history
- `docs/DEVELOPMENT.md` - Development info
- Docstrings in code - Implementation details

### Docstring Format

```python
def your_function(param1: str, param2: int) -> str:
    """
    One-line summary.
    
    Longer description explaining what this function does,
    when to use it, and any important considerations.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When something is invalid
        
    Example:
        >>> result = your_function("test", 42)
        >>> result
        "expected output"
    """
```

## Project Structure

Key directories:
- `llm_pricing/` - Main package code
- `llm_pricing/engine/` - Pricing calculation engine
- `llm_pricing/storage/` - Data storage layer
- `tests/` - Test suite
- `docs/` - Documentation
- `examples/` - Usage examples
- `data_versions/` - Reference snapshots

## Versioning

We follow semantic versioning: `MAJOR.MINOR.PATCH`
- `MAJOR`: Breaking changes
- `MINOR`: New features (backward compatible)
- `PATCH`: Bug fixes (backward compatible)

## Questions?

- Check existing issues and discussions
- Read the documentation in `docs/`
- Ask in a new GitHub issue with the `question` label

## Review Checklist for Maintainers

- [ ] Tests pass
- [ ] Code is formatted (black, ruff)
- [ ] Type hints present
- [ ] Docstrings added/updated
- [ ] CHANGELOG updated
- [ ] No breaking changes without version bump
- [ ] Documentation updated if needed

## Thank You!

Your contributions help make llm-pricing better for everyone. We appreciate your effort and time!
