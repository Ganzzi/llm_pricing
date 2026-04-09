# Phase 3: Simplified Repository Pattern

## Overview

The Repository Pattern provides a simplified data access abstraction layer between the API and the storage layer. Since we only need basic operations (`list_providers`, `list_models`, `add_provider`, `add_model`), this phase implements a lightweight repository without complex CRUD operations.

## Goals

- Provide clean data access for the simplified API
- Abstract storage details from business logic
- Support listing and adding operations only (no update/delete)
- Keep implementation minimal and maintainable

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     LLMPricing API                          │
│      calculate() | list_*() | add_*() | store_snapshot()   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Repository Layer                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              PricingRepository                       │   │
│  │  - list_providers()    - add_provider()             │   │
│  │  - list_models()       - add_model()                │   │
│  │  - get_model()                                       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Storage Layer                            │
│          LocalStorage + DataVersionManager                   │
└─────────────────────────────────────────────────────────────┘
```

## Implementation

### 3.1 Simplified Repository

```python
# src/llm_pricing/repository.py
"""Simplified repository for pricing data access."""
from typing import Optional
from pathlib import Path

from .models import (
    PricingDatabase,
    Provider,
    ModelInfo,
    ModelPrice,
    TieredPrice,
)
from .storage import LocalStorage, DataVersionManager


class PricingRepository:
    """Repository for accessing and modifying pricing data.
    
    Provides simplified operations:
    - list_providers(): Get all providers
    - list_models(): Get all models (optionally filtered by provider)
    - add_provider(): Add a new provider
    - add_model(): Add a new model
    - get_model(): Get specific model for pricing calculation
    
    Data is automatically loaded from local storage on initialization.
    Changes are persisted immediately to local storage.
    """
    
    def __init__(
        self,
        local_storage: LocalStorage,
        version_manager: DataVersionManager,
    ):
        """Initialize repository with storage backends.
        
        Args:
            local_storage: Local storage for working data
            version_manager: Manager for bundled data versions
        """
        self._local = local_storage
        self._versions = version_manager
        self._data: Optional[PricingDatabase] = None
    
    def _ensure_loaded(self) -> PricingDatabase:
        """Ensure data is loaded, initialize if needed."""
        if self._data is None:
            self._data = self._load_or_initialize()
        return self._data
    
    def _load_or_initialize(self) -> PricingDatabase:
        """Load from local storage or initialize from bundled snapshot."""
        # Try loading from local storage first
        if self._local.exists():
            return self._local.load()
        
        # Initialize from latest bundled snapshot
        latest = self._versions.find_latest()
        if latest is None:
            # No bundled snapshots, start with empty database
            return PricingDatabase(
                version="1.0.0",
                providers={},
            )
        
        # Load from bundled snapshot and save to local
        data = self._versions.load_snapshot(latest)
        self._local.save(data)
        return data
    
    def _save(self) -> None:
        """Save current data to local storage."""
        if self._data is not None:
            self._local.save(self._data)
    
    # === Public API Methods ===
    
    def list_providers(self) -> dict[str, Provider]:
        """Get all providers with their complete data.
        
        Returns:
            Dictionary mapping provider ID to Provider object.
            
        Example:
            >>> repo.list_providers()
            {
                'anthropic': Provider(id='anthropic', name='Anthropic', ...),
                'openai': Provider(id='openai', name='OpenAI', ...),
            }
        """
        data = self._ensure_loaded()
        return data.providers.copy()
    
    def list_models(
        self,
        provider_id: Optional[str] = None,
    ) -> list[ModelInfo]:
        """Get all models, optionally filtered by provider.
        
        Args:
            provider_id: Optional provider ID to filter by.
            
        Returns:
            List of ModelInfo objects.
            
        Example:
            >>> # All models
            >>> repo.list_models()
            [ModelInfo(id='claude-sonnet-4-20250514', ...), ...]
            
            >>> # Models for specific provider
            >>> repo.list_models(provider_id='anthropic')
            [ModelInfo(id='claude-sonnet-4-20250514', ...), ...]
        """
        data = self._ensure_loaded()
        models: list[ModelInfo] = []
        
        for p_id, provider in data.providers.items():
            if provider_id is not None and p_id != provider_id:
                continue
            models.extend(provider.models.values())
        
        return models
    
    def get_model(
        self,
        provider_id: str,
        model_id: str,
    ) -> Optional[ModelInfo]:
        """Get a specific model for pricing calculation.
        
        Args:
            provider_id: Provider ID (e.g., 'anthropic')
            model_id: Model ID (e.g., 'claude-sonnet-4-20250514')
            
        Returns:
            ModelInfo if found, None otherwise.
        """
        data = self._ensure_loaded()
        provider = data.providers.get(provider_id)
        if provider is None:
            return None
        return provider.models.get(model_id)
    
    def get_provider(self, provider_id: str) -> Optional[Provider]:
        """Get a specific provider.
        
        Args:
            provider_id: Provider ID (e.g., 'anthropic')
            
        Returns:
            Provider if found, None otherwise.
        """
        data = self._ensure_loaded()
        return data.providers.get(provider_id)
    
    def add_provider(self, provider: Provider) -> Provider:
        """Add a new provider.
        
        Args:
            provider: Provider object to add.
            
        Returns:
            The added provider.
            
        Raises:
            ValueError: If provider already exists.
            
        Example:
            >>> provider = Provider(
            ...     id='my-provider',
            ...     name='My Provider',
            ...     models={},
            ... )
            >>> repo.add_provider(provider)
        """
        data = self._ensure_loaded()
        
        if provider.id in data.providers:
            raise ValueError(f"Provider '{provider.id}' already exists")
        
        data.providers[provider.id] = provider
        self._save()
        return provider
    
    def add_model(
        self,
        provider_id: str,
        model: ModelInfo,
    ) -> ModelInfo:
        """Add a new model to a provider.
        
        Args:
            provider_id: Provider ID to add model to.
            model: ModelInfo object to add.
            
        Returns:
            The added model.
            
        Raises:
            ValueError: If provider doesn't exist or model already exists.
            
        Example:
            >>> model = ModelInfo(
            ...     id='my-model',
            ...     name='My Model',
            ...     price=ModelPrice(
            ...         input=TieredPrice(base=Decimal('0.003')),
            ...         output=TieredPrice(base=Decimal('0.015')),
            ...     ),
            ... )
            >>> repo.add_model('my-provider', model)
        """
        data = self._ensure_loaded()
        
        if provider_id not in data.providers:
            raise ValueError(f"Provider '{provider_id}' not found")
        
        provider = data.providers[provider_id]
        if model.id in provider.models:
            raise ValueError(
                f"Model '{model.id}' already exists for provider '{provider_id}'"
            )
        
        provider.models[model.id] = model
        self._save()
        return model
    
    def reload(self) -> None:
        """Reload data from local storage.
        
        Useful after external changes to local storage.
        """
        self._data = None
        self._ensure_loaded()
    
    @property
    def database(self) -> PricingDatabase:
        """Get the underlying database (for snapshot creation)."""
        return self._ensure_loaded()
```

### 3.2 Repository Factory

```python
# src/llm_pricing/repository.py (continued)

def create_repository(
    local_path: Optional[Path] = None,
    package_root: Optional[Path] = None,
) -> PricingRepository:
    """Factory function to create a repository with default configuration.
    
    Args:
        local_path: Custom path for local storage (default: ~/.llm_pricing/data.json)
        package_root: Custom package root for bundled snapshots
        
    Returns:
        Configured PricingRepository instance.
        
    Example:
        >>> # Default configuration
        >>> repo = create_repository()
        
        >>> # Custom paths
        >>> repo = create_repository(
        ...     local_path=Path('/custom/data.json'),
        ...     package_root=Path('/custom/package'),
        ... )
    """
    local_storage = LocalStorage(path=local_path)
    version_manager = DataVersionManager(package_root=package_root)
    
    return PricingRepository(
        local_storage=local_storage,
        version_manager=version_manager,
    )
```

## File Structure After Phase 3

```
src/llm_pricing/
├── __init__.py
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
└── repository.py           # NEW - Single file, simplified
```

## Usage Examples

### Basic Repository Usage

```python
from llm_pricing import create_repository

# Create repository with defaults
repo = create_repository()

# List all providers
providers = repo.list_providers()
for provider_id, provider in providers.items():
    print(f"{provider_id}: {provider.name}")
    
# List all models
models = repo.list_models()
print(f"Total models: {len(models)}")

# List models for specific provider
anthropic_models = repo.list_models(provider_id='anthropic')
for model in anthropic_models:
    print(f"  {model.id}: {model.name}")
```

### Adding Custom Provider and Model

```python
from decimal import Decimal
from llm_pricing import create_repository
from llm_pricing.models import Provider, ModelInfo, ModelPrice, TieredPrice

repo = create_repository()

# Add a custom provider
provider = Provider(
    id='my-company',
    name='My Company',
    models={},
)
repo.add_provider(provider)

# Add a custom model
model = ModelInfo(
    id='my-model-v1',
    name='My Model V1',
    price=ModelPrice(
        input=TieredPrice(base=Decimal('0.001')),
        output=TieredPrice(base=Decimal('0.005')),
    ),
)
repo.add_model('my-company', model)
```

### Getting Model for Pricing Calculation

```python
from llm_pricing import create_repository

repo = create_repository()

# Get specific model for calculation
model = repo.get_model('anthropic', 'claude-sonnet-4-20250514')
if model:
    print(f"Input price: ${model.price.input.base}/M tokens")
    print(f"Output price: ${model.price.output.base}/M tokens")
```

## Test Cases

### Unit Tests

```python
# tests/test_repository.py
import pytest
from decimal import Decimal
from pathlib import Path
import tempfile
import json

from llm_pricing.repository import PricingRepository, create_repository
from llm_pricing.storage import LocalStorage, DataVersionManager
from llm_pricing.models import (
    PricingDatabase,
    Provider,
    ModelInfo,
    ModelPrice,
    TieredPrice,
)


class TestPricingRepository:
    """Tests for PricingRepository."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def sample_database(self) -> PricingDatabase:
        """Create sample database for testing."""
        return PricingDatabase(
            version="1.0.0",
            providers={
                "anthropic": Provider(
                    id="anthropic",
                    name="Anthropic",
                    models={
                        "claude-3-opus": ModelInfo(
                            id="claude-3-opus",
                            name="Claude 3 Opus",
                            price=ModelPrice(
                                input=TieredPrice(base=Decimal("15.0")),
                                output=TieredPrice(base=Decimal("75.0")),
                            ),
                        ),
                    },
                ),
            },
        )
    
    @pytest.fixture
    def repo_with_data(self, temp_dir, sample_database):
        """Create repository with sample data."""
        local_path = temp_dir / "local" / "data.json"
        versions_dir = temp_dir / "versions"
        versions_dir.mkdir(parents=True)
        
        # Save sample data as bundled snapshot
        snapshot_path = versions_dir / "2025-01-15_120000.json"
        snapshot_path.write_text(
            sample_database.model_dump_json(indent=2)
        )
        
        local_storage = LocalStorage(path=local_path)
        version_manager = DataVersionManager(versions_dir=versions_dir)
        
        return PricingRepository(local_storage, version_manager)
    
    # === Test list_providers ===
    
    def test_list_providers_returns_all(self, repo_with_data):
        """Test listing all providers."""
        providers = repo_with_data.list_providers()
        
        assert "anthropic" in providers
        assert providers["anthropic"].name == "Anthropic"
    
    def test_list_providers_returns_copy(self, repo_with_data):
        """Test that list_providers returns a copy, not reference."""
        providers1 = repo_with_data.list_providers()
        providers2 = repo_with_data.list_providers()
        
        # Modify one, other should be unaffected
        providers1["anthropic"] = None
        assert providers2["anthropic"] is not None
    
    # === Test list_models ===
    
    def test_list_models_all(self, repo_with_data):
        """Test listing all models."""
        models = repo_with_data.list_models()
        
        assert len(models) == 1
        assert models[0].id == "claude-3-opus"
    
    def test_list_models_by_provider(self, repo_with_data):
        """Test listing models for specific provider."""
        models = repo_with_data.list_models(provider_id="anthropic")
        
        assert len(models) == 1
        assert models[0].id == "claude-3-opus"
    
    def test_list_models_unknown_provider(self, repo_with_data):
        """Test listing models for unknown provider."""
        models = repo_with_data.list_models(provider_id="unknown")
        
        assert models == []
    
    # === Test get_model ===
    
    def test_get_model_found(self, repo_with_data):
        """Test getting existing model."""
        model = repo_with_data.get_model("anthropic", "claude-3-opus")
        
        assert model is not None
        assert model.id == "claude-3-opus"
        assert model.price.input.base == Decimal("15.0")
    
    def test_get_model_not_found(self, repo_with_data):
        """Test getting non-existent model."""
        model = repo_with_data.get_model("anthropic", "nonexistent")
        
        assert model is None
    
    def test_get_model_unknown_provider(self, repo_with_data):
        """Test getting model with unknown provider."""
        model = repo_with_data.get_model("unknown", "some-model")
        
        assert model is None
    
    # === Test add_provider ===
    
    def test_add_provider_success(self, repo_with_data):
        """Test adding new provider."""
        new_provider = Provider(
            id="openai",
            name="OpenAI",
            models={},
        )
        
        result = repo_with_data.add_provider(new_provider)
        
        assert result.id == "openai"
        assert "openai" in repo_with_data.list_providers()
    
    def test_add_provider_duplicate_raises(self, repo_with_data):
        """Test adding duplicate provider raises error."""
        duplicate = Provider(
            id="anthropic",  # Already exists
            name="Anthropic Clone",
            models={},
        )
        
        with pytest.raises(ValueError, match="already exists"):
            repo_with_data.add_provider(duplicate)
    
    def test_add_provider_persists(self, repo_with_data):
        """Test that added provider is persisted."""
        new_provider = Provider(id="new", name="New", models={})
        repo_with_data.add_provider(new_provider)
        
        # Reload and verify
        repo_with_data.reload()
        providers = repo_with_data.list_providers()
        
        assert "new" in providers
    
    # === Test add_model ===
    
    def test_add_model_success(self, repo_with_data):
        """Test adding new model."""
        new_model = ModelInfo(
            id="claude-3-sonnet",
            name="Claude 3 Sonnet",
            price=ModelPrice(
                input=TieredPrice(base=Decimal("3.0")),
                output=TieredPrice(base=Decimal("15.0")),
            ),
        )
        
        result = repo_with_data.add_model("anthropic", new_model)
        
        assert result.id == "claude-3-sonnet"
        model = repo_with_data.get_model("anthropic", "claude-3-sonnet")
        assert model is not None
    
    def test_add_model_unknown_provider_raises(self, repo_with_data):
        """Test adding model to unknown provider raises error."""
        model = ModelInfo(
            id="test",
            name="Test",
            price=ModelPrice(
                input=TieredPrice(base=Decimal("1.0")),
                output=TieredPrice(base=Decimal("1.0")),
            ),
        )
        
        with pytest.raises(ValueError, match="not found"):
            repo_with_data.add_model("unknown", model)
    
    def test_add_model_duplicate_raises(self, repo_with_data):
        """Test adding duplicate model raises error."""
        duplicate = ModelInfo(
            id="claude-3-opus",  # Already exists
            name="Duplicate",
            price=ModelPrice(
                input=TieredPrice(base=Decimal("1.0")),
                output=TieredPrice(base=Decimal("1.0")),
            ),
        )
        
        with pytest.raises(ValueError, match="already exists"):
            repo_with_data.add_model("anthropic", duplicate)
    
    def test_add_model_persists(self, repo_with_data):
        """Test that added model is persisted."""
        new_model = ModelInfo(
            id="new-model",
            name="New Model",
            price=ModelPrice(
                input=TieredPrice(base=Decimal("1.0")),
                output=TieredPrice(base=Decimal("1.0")),
            ),
        )
        repo_with_data.add_model("anthropic", new_model)
        
        # Reload and verify
        repo_with_data.reload()
        model = repo_with_data.get_model("anthropic", "new-model")
        
        assert model is not None


class TestRepositoryInitialization:
    """Tests for repository initialization behavior."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_init_from_bundled_snapshot(self, temp_dir):
        """Test initialization from bundled snapshot when no local data."""
        local_path = temp_dir / "local" / "data.json"
        versions_dir = temp_dir / "versions"
        versions_dir.mkdir()
        
        # Create bundled snapshot
        snapshot_data = PricingDatabase(
            version="1.0.0",
            providers={
                "test": Provider(id="test", name="Test", models={}),
            },
        )
        (versions_dir / "2025-01-15_120000.json").write_text(
            snapshot_data.model_dump_json()
        )
        
        local_storage = LocalStorage(path=local_path)
        version_manager = DataVersionManager(versions_dir=versions_dir)
        repo = PricingRepository(local_storage, version_manager)
        
        providers = repo.list_providers()
        assert "test" in providers
        
        # Local file should now exist
        assert local_path.exists()
    
    def test_init_from_local_storage(self, temp_dir):
        """Test initialization from existing local storage."""
        local_path = temp_dir / "local" / "data.json"
        local_path.parent.mkdir(parents=True)
        
        # Create local data (different from bundled)
        local_data = PricingDatabase(
            version="2.0.0",
            providers={
                "local": Provider(id="local", name="Local", models={}),
            },
        )
        local_path.write_text(local_data.model_dump_json())
        
        # Create bundled snapshot (should be ignored)
        versions_dir = temp_dir / "versions"
        versions_dir.mkdir()
        bundled_data = PricingDatabase(
            version="1.0.0",
            providers={
                "bundled": Provider(id="bundled", name="Bundled", models={}),
            },
        )
        (versions_dir / "2025-01-15_120000.json").write_text(
            bundled_data.model_dump_json()
        )
        
        local_storage = LocalStorage(path=local_path)
        version_manager = DataVersionManager(versions_dir=versions_dir)
        repo = PricingRepository(local_storage, version_manager)
        
        providers = repo.list_providers()
        # Should use local data, not bundled
        assert "local" in providers
        assert "bundled" not in providers
    
    def test_init_empty_when_no_data(self, temp_dir):
        """Test initialization with empty database when no data available."""
        local_path = temp_dir / "local" / "data.json"
        versions_dir = temp_dir / "versions"
        versions_dir.mkdir()  # Empty versions directory
        
        local_storage = LocalStorage(path=local_path)
        version_manager = DataVersionManager(versions_dir=versions_dir)
        repo = PricingRepository(local_storage, version_manager)
        
        providers = repo.list_providers()
        assert providers == {}


class TestCreateRepository:
    """Tests for create_repository factory function."""
    
    def test_create_with_defaults(self, tmp_path, monkeypatch):
        """Test creating repository with default configuration."""
        # Redirect home directory to temp
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        
        repo = create_repository()
        
        # Should not raise
        providers = repo.list_providers()
        assert isinstance(providers, dict)
    
    def test_create_with_custom_paths(self, tmp_path):
        """Test creating repository with custom paths."""
        local_path = tmp_path / "custom" / "data.json"
        
        repo = create_repository(local_path=local_path)
        
        # Add data to verify custom path is used
        repo.add_provider(Provider(id="test", name="Test", models={}))
        
        assert local_path.exists()
```

## Integration with Storage Layer

### How Repository Uses Storage

```python
# The repository delegates storage operations to the storage layer:

class PricingRepository:
    def __init__(self, local_storage, version_manager):
        self._local = local_storage      # For read/write operations
        self._versions = version_manager  # For snapshot management
    
    def _load_or_initialize(self):
        # 1. Try local storage first
        if self._local.exists():
            return self._local.load()
        
        # 2. Fall back to bundled snapshots
        latest = self._versions.find_latest()
        if latest:
            data = self._versions.load_snapshot(latest)
            self._local.save(data)  # Copy to local for future use
            return data
        
        # 3. Empty database if nothing available
        return PricingDatabase(version="1.0.0", providers={})
```

### Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    First-time Initialization                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. Check local storage exists?                                   │
│     ~/.llm_pricing/data.json                                      │
│          │                                                        │
│          ├── YES → Load from local storage                        │
│          │                                                        │
│          └── NO  → Check bundled snapshots                        │
│                    llm_pricing/data_versions/*.json               │
│                         │                                         │
│                         ├── Found → Load latest, save to local    │
│                         │                                         │
│                         └── Empty → Create empty database         │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    Add Provider/Model Flow                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. add_provider() or add_model() called                          │
│          │                                                        │
│          ▼                                                        │
│  2. Validate (check duplicates, provider exists)                  │
│          │                                                        │
│          ▼                                                        │
│  3. Update in-memory data                                         │
│          │                                                        │
│          ▼                                                        │
│  4. Save to local storage immediately                             │
│     ~/.llm_pricing/data.json                                      │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Dependencies

### Phase Dependencies

- **Phase 1** (Data Models): Uses `PricingDatabase`, `Provider`, `ModelInfo`, etc.
- **Phase 2** (Storage): Uses `LocalStorage` and `DataVersionManager`

### Python Dependencies

No additional dependencies beyond Phase 1 and 2.

## Acceptance Criteria

- [ ] `PricingRepository` class implemented with all methods
- [ ] `create_repository()` factory function working
- [ ] Repository loads from local storage when available
- [ ] Repository initializes from bundled snapshot when no local data
- [ ] Repository creates empty database when no data sources available
- [ ] `list_providers()` returns all providers
- [ ] `list_models()` returns all models, with optional filtering
- [ ] `get_model()` returns specific model or None
- [ ] `add_provider()` adds new provider and persists
- [ ] `add_model()` adds new model to existing provider and persists
- [ ] Duplicate provider/model raises `ValueError`
- [ ] Unknown provider for `add_model()` raises `ValueError`
- [ ] All unit tests passing
- [ ] Integration tests with storage layer passing

## Notes

### Design Decisions

1. **Single Repository Class**: Unlike traditional repository patterns with separate repositories per entity, we use a single `PricingRepository` since our data model is relatively simple and interconnected.

2. **No Update/Delete Operations**: Per requirements, we only support adding data, not modifying or removing. This simplifies the implementation and matches the use case.

3. **Immediate Persistence**: Changes are saved immediately to local storage. No transaction support is needed for our use case.

4. **Copy on List**: `list_providers()` returns a copy of the dictionary to prevent accidental mutations of internal state.

5. **Lazy Loading**: Data is loaded only when first accessed, not on initialization.

## Next Phase

Phase 4 (Pricing Engine) will use this repository to retrieve model pricing data for cost calculations.
