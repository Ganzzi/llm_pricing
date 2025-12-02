# Phase 5: Snapshot Management

## Overview

Phase 5 implements the `store_snapshot()` functionality - creating a new snapshot from the current local data and saving it to the bundled `data_versions` folder. This allows users to persist their custom pricing data as a new version that gets bundled with the package.

## Goals

- Create snapshots from current local data
- Save snapshots to the `data_versions` folder
- Support datetime-based naming convention
- Coordinate between repository and storage layers

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   LLMPricing.store_snapshot()               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   SnapshotManager                            │
│  - create_snapshot(): Save current data to data_versions/   │
│  - list_snapshots(): List all available snapshots           │
│  - get_snapshot_info(): Get metadata about a snapshot       │
└─────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            ▼                                   ▼
┌───────────────────────┐         ┌───────────────────────────┐
│  PricingRepository    │         │    DataVersionManager     │
│  (provides database)  │         │    (stores snapshots)     │
└───────────────────────┘         └───────────────────────────┘
```

## Implementation

### 5.1 Snapshot Manager

```python
# src/llm_pricing/snapshot.py
"""Snapshot management for storing data versions."""
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .models import PricingDatabase
from .repository import PricingRepository
from .storage import DataVersionManager


@dataclass
class SnapshotInfo:
    """Information about a snapshot."""
    
    filename: str
    path: Path
    timestamp: datetime
    provider_count: int
    model_count: int


class SnapshotManager:
    """Manager for creating and listing snapshots.
    
    Snapshots are JSON files saved to the data_versions folder with
    datetime-based naming (e.g., 2025-01-15_120000.json).
    
    This allows users to persist their custom pricing data as versioned
    snapshots that can be bundled with the package for distribution.
    """
    
    def __init__(
        self,
        repository: PricingRepository,
        version_manager: DataVersionManager,
    ):
        """Initialize snapshot manager.
        
        Args:
            repository: Repository for accessing current data
            version_manager: Manager for data versions storage
        """
        self._repo = repository
        self._versions = version_manager
    
    def create_snapshot(
        self,
        timestamp: Optional[datetime] = None,
    ) -> SnapshotInfo:
        """Create a new snapshot from current local data.
        
        The snapshot is saved to the data_versions folder with a
        datetime-based filename.
        
        Args:
            timestamp: Optional timestamp to use (defaults to now)
            
        Returns:
            SnapshotInfo with details about the created snapshot
            
        Example:
            >>> manager = SnapshotManager(repo, version_manager)
            >>> info = manager.create_snapshot()
            >>> print(f"Created: {info.filename}")
            Created: 2025-01-15_143022.json
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Get current database from repository
        database = self._repo.database
        
        # Store snapshot using version manager
        snapshot_path = self._versions.store_snapshot(database, timestamp)
        
        # Calculate stats
        provider_count = len(database.providers)
        model_count = sum(
            len(p.models) for p in database.providers.values()
        )
        
        return SnapshotInfo(
            filename=snapshot_path.name,
            path=snapshot_path,
            timestamp=timestamp,
            provider_count=provider_count,
            model_count=model_count,
        )
    
    def list_snapshots(self) -> list[SnapshotInfo]:
        """List all available snapshots.
        
        Returns:
            List of SnapshotInfo sorted by timestamp (newest first)
            
        Example:
            >>> snapshots = manager.list_snapshots()
            >>> for s in snapshots:
            ...     print(f"{s.filename}: {s.provider_count} providers")
        """
        snapshots = []
        
        for filename in self._versions.list_versions():
            try:
                timestamp = self._parse_filename_timestamp(filename)
                path = self._versions.versions_dir / filename
                
                # Load snapshot to get stats
                database = self._versions.load_snapshot(filename)
                provider_count = len(database.providers)
                model_count = sum(
                    len(p.models) for p in database.providers.values()
                )
                
                snapshots.append(
                    SnapshotInfo(
                        filename=filename,
                        path=path,
                        timestamp=timestamp,
                        provider_count=provider_count,
                        model_count=model_count,
                    )
                )
            except (ValueError, Exception):
                # Skip invalid snapshot files
                continue
        
        # Sort by timestamp, newest first
        return sorted(snapshots, key=lambda s: s.timestamp, reverse=True)
    
    def get_snapshot_info(self, filename: str) -> Optional[SnapshotInfo]:
        """Get information about a specific snapshot.
        
        Args:
            filename: Snapshot filename (e.g., '2025-01-15_120000.json')
            
        Returns:
            SnapshotInfo if found, None otherwise
        """
        available = self._versions.list_versions()
        if filename not in available:
            return None
        
        try:
            timestamp = self._parse_filename_timestamp(filename)
            path = self._versions.versions_dir / filename
            database = self._versions.load_snapshot(filename)
            
            return SnapshotInfo(
                filename=filename,
                path=path,
                timestamp=timestamp,
                provider_count=len(database.providers),
                model_count=sum(
                    len(p.models) for p in database.providers.values()
                ),
            )
        except Exception:
            return None
    
    def _parse_filename_timestamp(self, filename: str) -> datetime:
        """Parse timestamp from snapshot filename.
        
        Args:
            filename: Filename like '2025-01-15_120000.json'
            
        Returns:
            Parsed datetime
        """
        # Remove .json extension
        name = filename.replace(".json", "")
        return datetime.strptime(name, "%Y-%m-%d_%H%M%S")


def create_snapshot_manager(
    repository: PricingRepository,
    version_manager: DataVersionManager,
) -> SnapshotManager:
    """Factory function to create a snapshot manager.
    
    Args:
        repository: Repository for accessing current data
        version_manager: Manager for data versions storage
        
    Returns:
        Configured SnapshotManager instance
    """
    return SnapshotManager(repository, version_manager)
```

### 5.2 Integration with Public API

The `store_snapshot()` method in the main `LLMPricing` class will delegate to `SnapshotManager`:

```python
# In LLMPricing class (Phase 6)
class LLMPricing:
    def __init__(self):
        self._repo = create_repository()
        self._snapshot_manager = SnapshotManager(
            self._repo,
            self._repo._versions,
        )
    
    def store_snapshot(self) -> SnapshotInfo:
        """Store current data as a new snapshot.
        
        Creates a new snapshot file in the data_versions folder with the
        current local data. The snapshot uses datetime-based naming.
        
        Returns:
            SnapshotInfo with details about the created snapshot
            
        Example:
            >>> pricing = LLMPricing()
            >>> # Make some changes...
            >>> pricing.add_provider(...)
            >>> pricing.add_model(...)
            >>> # Store as snapshot
            >>> info = pricing.store_snapshot()
            >>> print(f"Saved: {info.filename}")
        """
        return self._snapshot_manager.create_snapshot()
```

## File Structure After Phase 5

```
src/llm_pricing/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── ...
├── storage/
│   ├── __init__.py
│   ├── local.py
│   └── versions.py
├── repository.py
├── engine/
│   ├── __init__.py
│   └── ...
└── snapshot.py             # NEW
```

## Usage Examples

### Creating a Snapshot

```python
from llm_pricing import LLMPricing

pricing = LLMPricing()

# Add custom data
pricing.add_provider(Provider(id='my-provider', name='My Provider', models={}))
pricing.add_model('my-provider', ModelInfo(...))

# Store as snapshot
info = pricing.store_snapshot()
print(f"Created snapshot: {info.filename}")
print(f"  Providers: {info.provider_count}")
print(f"  Models: {info.model_count}")
print(f"  Path: {info.path}")
```

### Listing Available Snapshots

```python
from llm_pricing.snapshot import SnapshotManager

# Direct usage of SnapshotManager (for advanced use)
manager = SnapshotManager(repo, version_manager)

snapshots = manager.list_snapshots()
for s in snapshots:
    print(f"{s.filename}")
    print(f"  Timestamp: {s.timestamp}")
    print(f"  Providers: {s.provider_count}")
    print(f"  Models: {s.model_count}")
```

## Test Cases

### Unit Tests

```python
# tests/test_snapshot.py
import pytest
from datetime import datetime
from pathlib import Path
import tempfile

from llm_pricing.models import PricingDatabase, Provider, ModelInfo, ModelPrice, TieredPrice
from llm_pricing.storage import LocalStorage, DataVersionManager
from llm_pricing.repository import PricingRepository
from llm_pricing.snapshot import SnapshotManager, SnapshotInfo


class TestSnapshotManager:
    """Tests for SnapshotManager."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def sample_database(self):
        """Create sample database."""
        return PricingDatabase(
            version="1.0.0",
            providers={
                "anthropic": Provider(
                    id="anthropic",
                    name="Anthropic",
                    models={
                        "claude-3": ModelInfo(
                            id="claude-3",
                            name="Claude 3",
                            price=ModelPrice(
                                input=TieredPrice(base=Decimal("3.0")),
                                output=TieredPrice(base=Decimal("15.0")),
                            ),
                        ),
                    },
                ),
            },
        )
    
    @pytest.fixture
    def manager(self, temp_dir, sample_database):
        """Create snapshot manager with sample data."""
        local_path = temp_dir / "local" / "data.json"
        local_path.parent.mkdir(parents=True)
        local_path.write_text(sample_database.model_dump_json())
        
        versions_dir = temp_dir / "data_versions"
        versions_dir.mkdir()
        
        local_storage = LocalStorage(path=local_path)
        version_manager = DataVersionManager(versions_dir=versions_dir)
        repo = PricingRepository(local_storage, version_manager)
        
        return SnapshotManager(repo, version_manager)
    
    # === Test create_snapshot ===
    
    def test_create_snapshot_creates_file(self, manager, temp_dir):
        """Test that create_snapshot creates a new file."""
        info = manager.create_snapshot()
        
        assert info.path.exists()
        assert info.filename.endswith(".json")
    
    def test_create_snapshot_uses_datetime_name(self, manager):
        """Test that snapshot uses datetime-based filename."""
        timestamp = datetime(2025, 1, 15, 12, 30, 45)
        info = manager.create_snapshot(timestamp=timestamp)
        
        assert info.filename == "2025-01-15_123045.json"
    
    def test_create_snapshot_returns_correct_stats(self, manager):
        """Test that snapshot info has correct statistics."""
        info = manager.create_snapshot()
        
        assert info.provider_count == 1
        assert info.model_count == 1
    
    def test_create_snapshot_contains_valid_data(self, manager, temp_dir):
        """Test that created snapshot contains valid JSON."""
        info = manager.create_snapshot()
        
        # Load and verify
        data = PricingDatabase.model_validate_json(info.path.read_text())
        assert "anthropic" in data.providers
    
    # === Test list_snapshots ===
    
    def test_list_snapshots_empty(self, manager):
        """Test listing when no snapshots exist."""
        snapshots = manager.list_snapshots()
        assert snapshots == []
    
    def test_list_snapshots_after_create(self, manager):
        """Test listing after creating a snapshot."""
        manager.create_snapshot()
        
        snapshots = manager.list_snapshots()
        assert len(snapshots) == 1
    
    def test_list_snapshots_sorted_newest_first(self, manager):
        """Test that snapshots are sorted newest first."""
        manager.create_snapshot(timestamp=datetime(2025, 1, 10))
        manager.create_snapshot(timestamp=datetime(2025, 1, 15))
        manager.create_snapshot(timestamp=datetime(2025, 1, 12))
        
        snapshots = manager.list_snapshots()
        
        assert len(snapshots) == 3
        assert snapshots[0].filename == "2025-01-15_000000.json"
        assert snapshots[1].filename == "2025-01-12_000000.json"
        assert snapshots[2].filename == "2025-01-10_000000.json"
    
    # === Test get_snapshot_info ===
    
    def test_get_snapshot_info_found(self, manager):
        """Test getting info for existing snapshot."""
        created = manager.create_snapshot()
        
        info = manager.get_snapshot_info(created.filename)
        
        assert info is not None
        assert info.filename == created.filename
    
    def test_get_snapshot_info_not_found(self, manager):
        """Test getting info for non-existent snapshot."""
        info = manager.get_snapshot_info("nonexistent.json")
        
        assert info is None


class TestSnapshotInfo:
    """Tests for SnapshotInfo dataclass."""
    
    def test_snapshot_info_fields(self):
        """Test SnapshotInfo fields."""
        info = SnapshotInfo(
            filename="2025-01-15_120000.json",
            path=Path("/some/path/2025-01-15_120000.json"),
            timestamp=datetime(2025, 1, 15, 12, 0, 0),
            provider_count=5,
            model_count=100,
        )
        
        assert info.filename == "2025-01-15_120000.json"
        assert info.provider_count == 5
        assert info.model_count == 100
```

## Dependencies

### Phase Dependencies

- **Phase 1** (Data Models): Uses `PricingDatabase` for serialization
- **Phase 2** (Storage): Uses `DataVersionManager.store_snapshot()`
- **Phase 3** (Repository): Uses `PricingRepository.database` property

### Python Dependencies

Only standard library (`datetime`, `pathlib`, `dataclasses`).

## Acceptance Criteria

- [ ] `SnapshotManager` class implemented
- [ ] `create_snapshot()` creates valid JSON file
- [ ] Snapshot filenames follow datetime convention
- [ ] `list_snapshots()` returns sorted list
- [ ] `get_snapshot_info()` returns correct metadata
- [ ] Snapshots contain complete database data
- [ ] All unit tests passing

## Notes

### Design Decisions

1. **Datetime-based Naming**: Snapshots use `YYYY-MM-DD_HHMMSS.json` format for easy sorting and identification.

2. **Statistics in Info**: `SnapshotInfo` includes provider/model counts for quick overview without loading full data.

3. **Factory Function**: `create_snapshot_manager()` provides easy creation with dependency injection for testing.

4. **Integration Point**: The main `LLMPricing` class (Phase 6) will expose this through a simple `store_snapshot()` method.

## Next Phase

Phase 6 (Public API) will combine all components into the unified `LLMPricing` class with the simple API:
- `calculate()`
- `list_providers()`
- `list_models()`
- `add_provider()`
- `add_model()`
- `store_snapshot()`
