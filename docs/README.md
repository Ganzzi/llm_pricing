# Documentation Index

Welcome to the llm-pricing documentation. This guide will help you navigate all available resources.

## Quick Links

- **[README.md](../README.md)** - Project overview, quick start, and examples
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - How to contribute to the project
- **[DEVELOPMENT.md](../DEVELOPMENT.md)** - Development setup and guide
- **[CHANGELOG.md](../CHANGELOG.md)** - Version history and release notes

## Documentation Files

### User Documentation

- **[API.md](API.md)** - Complete API reference with all methods, classes, and examples

### Integration Guides

- **[DJANGO_INTEGRATION.md](DJANGO_INTEGRATION.md)** - Integrating with Django projects
- **[DJANGO_APP_INTEGRATION.md](DJANGO_APP_INTEGRATION.md)** - Advanced Django application integration

### Architecture & Planning

- **[plan/README.md](plan/README.md)** - Overview of the implementation phases
- **[plan/PHASE_1_DATA_MODELS.md](plan/PHASE_1_DATA_MODELS.md)** - Data model design
- **[plan/PHASE_2_STORAGE.md](plan/PHASE_2_STORAGE.md)** - Storage layer architecture
- **[plan/PHASE_3_REPOSITORY.md](plan/PHASE_3_REPOSITORY.md)** - Repository pattern implementation
- **[plan/PHASE_4_PRICING_ENGINE.md](plan/PHASE_4_PRICING_ENGINE.md)** - Pricing calculation engine
- **[plan/PHASE_5_SNAPSHOT.md](plan/PHASE_5_SNAPSHOT.md)** - Snapshot management system
- **[plan/PHASE_6_PUBLIC_API.md](plan/PHASE_6_PUBLIC_API.md)** - Public API design
- **[plan/PROGRESS_CHECKLIST.md](plan/PROGRESS_CHECKLIST.md)** - Implementation progress tracker

## Getting Started

### For New Users

1. Start with [README.md](../README.md) for an overview
2. Follow the "Quick Start" section
3. Check out the [examples/comprehensive_example.py](../examples/comprehensive_example.py)
4. Reference [API.md](API.md) for detailed method documentation

### For Developers

1. Read [DEVELOPMENT.md](../DEVELOPMENT.md) for environment setup
2. Review [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines
3. Understand the architecture in [plan/](plan/)
4. Look at tests in `tests/` for usage patterns

### For Django Integration

1. Start with [DJANGO_INTEGRATION.md](DJANGO_INTEGRATION.md)
2. For advanced usage, see [DJANGO_APP_INTEGRATION.md](DJANGO_APP_INTEGRATION.md)

## Document Purpose

| Document | Purpose | Audience |
|----------|---------|----------|
| README.md | Project overview, quick start | Everyone |
| API.md | Complete API reference | Users, Developers |
| CONTRIBUTING.md | How to contribute | Developers |
| DEVELOPMENT.md | Dev environment, debugging | Developers |
| CHANGELOG.md | Version history | Everyone |
| DJANGO_INTEGRATION.md | Django setup | Django developers |
| DJANGO_APP_INTEGRATION.md | Advanced Django usage | Django developers |
| plan/* | Architecture decisions | Developers, Maintainers |

## Key Concepts

### Data Models

The package uses Pydantic for type-safe data models:
- `Provider` - API provider (OpenAI, Anthropic, etc.)
- `ModelInfo` - Model with pricing and rate limits
- `ModelPrice` - Pricing configuration
- `TokenUsage` - Input/output token counts
- `PricingResult` - Calculation results

### Architecture Layers

```
LLMPricing (Public API)
    ↓
PricingEngine (Calculations)
    ↓
PricingRepository (Data Access)
    ↓
LocalStorage / DataVersionManager (Persistence)
    ↓
File System (data.json)
```

### Storage Model

- **data.json** - Working data (git-ignored, persistent)
- **data_versions/** - Snapshots (git-tracked, reference)
- Auto-load latest snapshot on first run

## Common Tasks

### Find API Documentation
→ See [API.md](API.md)

### Learn to contribute
→ See [CONTRIBUTING.md](../CONTRIBUTING.md)

### Set up development environment
→ See [DEVELOPMENT.md](../DEVELOPMENT.md)

### Understand architecture
→ See [plan/README.md](plan/README.md)

### Integrate with Django
→ See [DJANGO_INTEGRATION.md](DJANGO_INTEGRATION.md)

### View implementation progress
→ See [plan/PROGRESS_CHECKLIST.md](plan/PROGRESS_CHECKLIST.md)

## Version History

See [CHANGELOG.md](../CHANGELOG.md) for complete version history and release notes.

## Support

- **Issues**: Open an issue on GitHub for bugs or features
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check the docs/ folder first
- **Examples**: See examples/comprehensive_example.py

## License

MIT - See [LICENSE](../LICENSE)
