# Changelog

All notable changes to the `llm-pricing` project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure documentation
- GitHub Actions CI/CD workflow
- Comprehensive contribution guidelines

### Changed
- Enhanced README with GitHub project structure
- Updated .gitignore for better IDE and development tool support

## [0.1.0] - 2025-12-02

### Added

#### Core API
- `LLMPricing` class with main public API
- `calculate()` - Calculate cost for token usage with support for flat and tiered pricing
- `list_providers()` - Get all available providers
- `list_models()` - Get models with optional provider filtering
- `add_provider()` - Add new provider to database
- `add_model()` - Add new model to provider
- `delete_provider()` - Delete provider and associated models
- `delete_model()` - Delete specific model
- `store_snapshot()` - Save current pricing data as snapshot
- `validate()` - Validate provider and model exist before calculation

#### Data Models
- `Provider` - API provider with tiers and models
- `ProviderTier` - Tier configuration (Free, Pro, Enterprise, etc.)
- `ModelInfo` - Model information with pricing and rate limits
- `ModelPrice` - Simple and tiered pricing configuration
- `TieredPrice` - Context-based pricing with multiple tiers
- `PriceTier` - Individual pricing tier definition
- `ModelRateLimits` - Rate limits per model per tier
- `TokenUsage` - Token usage specification
- `PricingResult` - Calculation result with cost breakdown

#### Storage Layer
- `LocalStorage` - File-based data persistence
- `DataVersionManager` - Snapshot management with datetime-based naming
- Auto-load latest snapshot on first run
- Persistent `data.json` with git-ignore support

#### Pricing Engine
- Flat rate pricing calculations
- Tiered pricing support (like Claude Sonnet 4.5)
- Cache pricing (read and write tokens)
- Cost breakdown with detailed pricing information
- Tier multipliers support

#### Snapshot Management
- `SnapshotManager` for creating and listing snapshots
- Datetime-based snapshot naming: `YYYY-MM-DD_HHMMSS_ffffff.json`
- Snapshot information retrieval

#### Utilities
- `calculate_cost()` convenience function for quick calculations
- Comprehensive API documentation in `docs/API.md`
- Development guide in `DEVELOPMENT.md`
- Contribution guidelines in `CONTRIBUTING.md`

### Features

- **Provider Tiers**: Support for Free, Pro, Enterprise, and custom tiers
- **Model-Based Rate Limiters**: Different limits per model per tier
- **Tiered Pricing**: Context-based pricing that changes at token thresholds
- **Local Data**: Working data persists in `data.json` (git-ignored)
- **Snapshots**: Reference snapshots in `data_versions/` (git-tracked)
- **Type Safety**: Full Pydantic validation for all data models
- **Decimal Precision**: Uses Python `Decimal` for precise money calculations
- **Flexible Architecture**: Layered design allows easy extension

### Testing
- 137+ comprehensive test cases
- >88% code coverage
- Unit tests for all components:
  - Data models and validation
  - Storage layer
  - Repository layer
  - Pricing engine (flat and tiered)
  - Snapshot management
  - Public API methods

### Documentation
- Comprehensive README with quick start and examples
- Full API reference with method signatures and examples
- Development guide with environment setup and debugging
- Contributing guidelines for open source collaboration
- Architecture documentation in `docs/plan/`

### Project Setup
- Python 3.9+ support
- Pydantic v2 for data validation
- Development tools: pytest, black, ruff, mypy
- Structured as standalone GitHub project (not published to PyPI)

## [0.0.1] - Initial Concept

### Initial Design
- Project concept and planning
- Phase-based implementation plan
- Architecture design documents
