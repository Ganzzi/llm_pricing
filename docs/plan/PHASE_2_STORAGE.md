# Phase 2: Storage Layer

## Overview

This phase implements the storage layer with two key concepts:

1. **Data Versions** - Bundled snapshot files in the package's `data_versions/` folder (shipped with code)
2. **Local Storage** - User's working data at `~/.llm_pricing/data.json`

**Duration:** 1-2 days

---

## 🎯 Goals

- [ ] Implement `DataVersionManager` for bundled snapshots
- [ ] Implement `LocalStorage` for user's working data
- [ ] Auto-load latest data version on init
- [ ] Create `store_snapshot()` to save local data as new data version
- [ ] Handle errors gracefully
- [ ] Write unit tests

---

## 📊 Storage Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Storage Layer                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────┐     ┌───────────────────────────────┐ │
│  │   DataVersionManager │     │       LocalStorage            │ │
│  │                      │     │                               │ │
│  │  package/data_vers./ │     │  ~/.llm_pricing/data.json     │ │
│  │  ├─ 2025-11-30_...  │ ──► │  (user's working copy)        │ │
│  │  └─ 2025-11-29_...  │     │                               │ │
│  │                      │     │                               │ │
│  │  (bundled, git track)│     │  (runtime modifications)      │ │
│  └──────────────────────┘     └───────────────────────────────┘ │
│           │                              │                       │
│           │ get_latest()                 │ store_snapshot()      │
│           ▼                              ▼                       │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                 PricingDatabase                              ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### File Locations

```
llm_pricing/                        # Package root (Git repo)
├── llm_pricing/
│   └── ...
├── data_versions/                  # Bundled with package (Git tracked)
│   ├── 2025-11-30_143022.json     # Snapshot files
│   ├── 2025-11-29_090000.json
│   └── ...
└── ...

~/.llm_pricing/                     # User's local directory
└── data.json                       # Working data (runtime modifications)
```

---

## 📝 Implementation

### File: `storage/config.py`

```python
"""Storage configuration."""

from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class StorageConfig:
    """Configuration for storage locations."""
    
    # User's local data directory
    local_data_dir: Path = field(
        default_factory=lambda: Path.home() / ".llm_pricing"
    )
    
    # Package's data versions directory (relative to package)
    data_versions_dir: Path | None = None  # Auto-detected
    
    @property
    def local_data_file(self) -> Path:
        """Path to user's working data file."""
        return self.local_data_dir / "data.json"
    
    def get_data_versions_dir(self) -> Path:
        """Get the data_versions directory (bundled with package)."""
        if self.data_versions_dir:
            return self.data_versions_dir
        
        # Auto-detect: package root / data_versions
        package_dir = Path(__file__).parent.parent.parent
        return package_dir / "data_versions"
    
    def ensure_local_dir(self) -> None:
        """Ensure local data directory exists."""
        self.local_data_dir.mkdir(parents=True, exist_ok=True)
```

---

### File: `storage/data_versions.py`

```python
"""Data version management - bundled snapshots shipped with package."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..types import PricingDatabase
from ..exceptions import StorageError
from .config import StorageConfig


class DataVersionManager:
    """
    Manages data version snapshots bundled with the package.
    
    Snapshots are stored in `data_versions/` folder at the package root.
    Files are named with datetime: YYYY-MM-DD_HHMMSS.json
    
    These files are:
    - Git tracked (committed to repository)
    - Shipped with the package
    - Read-only during normal use
    - Created via store_snapshot() from local data
    """
    
    FILENAME_FORMAT = "%Y-%m-%d_%H%M%S.json"
    
    def __init__(self, config: StorageConfig):
        self._config = config
        self._versions_dir = config.get_data_versions_dir()
    
    @property
    def versions_dir(self) -> Path:
        """Get the data versions directory."""
        return self._versions_dir
    
    def list_versions(self) -> list[Path]:
        """
        List all available data version files, sorted newest first.
        
        Returns:
            List of paths to version files, newest first
        """
        if not self._versions_dir.exists():
            return []
        
        files = list(self._versions_dir.glob("*.json"))
        # Sort by filename (datetime format ensures chronological order)
        return sorted(files, reverse=True)
    
    def get_latest_version(self) -> Optional[Path]:
        """
        Get the path to the latest data version file.
        
        Returns:
            Path to latest version file, or None if no versions exist
        """
        versions = self.list_versions()
        return versions[0] if versions else None
    
    def load_version(self, version_path: Path) -> PricingDatabase:
        """
        Load a specific data version.
        
        Args:
            version_path: Path to the version file
        
        Returns:
            PricingDatabase loaded from the file
        
        Raises:
            StorageError: If file cannot be read or parsed
        """
        try:
            with open(version_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PricingDatabase.model_validate(data)
        except FileNotFoundError:
            raise StorageError(f"Version file not found: {version_path}")
        except json.JSONDecodeError as e:
            raise StorageError(f"Invalid JSON in version file: {e}")
        except Exception as e:
            raise StorageError(f"Failed to load version: {e}")
    
    def load_latest(self) -> Optional[PricingDatabase]:
        """
        Load the latest data version.
        
        Returns:
            PricingDatabase from latest version, or None if no versions exist
        """
        latest = self.get_latest_version()
        if latest is None:
            return None
        return self.load_version(latest)
    
    def create_snapshot(self, database: PricingDatabase) -> Path:
        """
        Create a new data version snapshot.
        
        This saves the given database to a new file in data_versions/
        with a datetime-based filename.
        
        Args:
            database: PricingDatabase to save
        
        Returns:
            Path to the created snapshot file
        
        Note:
            This creates a file that should be committed to Git
            to be included in the package.
        """
        # Ensure directory exists
        self._versions_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with current datetime
        timestamp = datetime.now().strftime(self.FILENAME_FORMAT)
        snapshot_path = self._versions_dir / timestamp
        
        # Avoid overwriting (add suffix if needed)
        counter = 1
        while snapshot_path.exists():
            base = timestamp.replace(".json", f"_{counter}.json")
            snapshot_path = self._versions_dir / base
            counter += 1
        
        # Save with pretty formatting
        try:
            with open(snapshot_path, "w", encoding="utf-8") as f:
                json.dump(
                    database.model_dump(mode="json"),
                    f,
                    indent=2,
                    default=str,
                    ensure_ascii=False,
                )
        except Exception as e:
            raise StorageError(f"Failed to create snapshot: {e}")
        
        return snapshot_path
    
    def get_version_info(self, version_path: Path) -> dict:
        """
        Get metadata about a version file.
        
        Args:
            version_path: Path to version file
        
        Returns:
            Dict with version metadata
        """
        stat = version_path.stat()
        
        # Parse datetime from filename
        try:
            dt = datetime.strptime(
                version_path.stem, 
                self.FILENAME_FORMAT.replace(".json", "")
            )
        except ValueError:
            dt = datetime.fromtimestamp(stat.st_mtime)
        
        return {
            "path": str(version_path),
            "filename": version_path.name,
            "created_at": dt.isoformat(),
            "size_bytes": stat.st_size,
        }
```

---

### File: `storage/local_storage.py`

```python
"""Local storage for user's working data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..types import PricingDatabase
from ..exceptions import StorageError
from .config import StorageConfig


class LocalStorage:
    """
    Manages user's local working data.
    
    Location: ~/.llm_pricing/data.json
    
    This is where runtime modifications are stored.
    """
    
    def __init__(self, config: StorageConfig):
        self._config = config
    
    @property
    def data_file(self) -> Path:
        """Path to the local data file."""
        return self._config.local_data_file
    
    def exists(self) -> bool:
        """Check if local data file exists."""
        return self.data_file.exists()
    
    def load(self) -> Optional[PricingDatabase]:
        """
        Load data from local storage.
        
        Returns:
            PricingDatabase or None if file doesn't exist
        """
        if not self.exists():
            return None
        
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PricingDatabase.model_validate(data)
        except json.JSONDecodeError as e:
            raise StorageError(f"Invalid JSON in local data: {e}")
        except Exception as e:
            raise StorageError(f"Failed to load local data: {e}")
    
    def save(self, database: PricingDatabase) -> None:
        """
        Save data to local storage.
        
        Args:
            database: PricingDatabase to save
        """
        # Ensure directory exists
        self._config.ensure_local_dir()
        
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(
                    database.model_dump(mode="json"),
                    f,
                    indent=2,
                    default=str,
                    ensure_ascii=False,
                )
        except Exception as e:
            raise StorageError(f"Failed to save local data: {e}")
    
    def delete(self) -> bool:
        """
        Delete local data file.
        
        Returns:
            True if file was deleted, False if it didn't exist
        """
        if self.exists():
            self.data_file.unlink()
            return True
        return False
```

---

### File: `storage/__init__.py`

```python
"""Storage layer for LLM pricing data."""

from .config import StorageConfig
from .data_versions import DataVersionManager
from .local_storage import LocalStorage

__all__ = [
    "StorageConfig",
    "DataVersionManager",
    "LocalStorage",
]
```

---

### File: `exceptions.py`

```python
"""Custom exceptions for the pricing package."""


class LLMPricingError(Exception):
    """Base exception for all pricing errors."""
    pass


class StorageError(LLMPricingError):
    """Error in storage operations."""
    pass


class StorageNotFoundError(StorageError):
    """Storage file not found."""
    pass


class PricingError(LLMPricingError):
    """Error in pricing calculations."""
    pass


class ValidationError(LLMPricingError):
    """Data validation error."""
    pass
```

---

## 📊 Storage Flow

### Initialization Flow

```
LLMPricing.__init__()
    │
    ├─► LocalStorage.load()
    │       │
    │       └─► Returns existing local data if present
    │
    └─► DataVersionManager.load_latest()
            │
            └─► Loads bundled snapshot
            
If no local data exists:
    local_data = latest_version_data
    LocalStorage.save(local_data)
```

### store_snapshot() Flow

```
LLMPricing.store_snapshot()
    │
    ├─► LocalStorage.load()      # Get current local data
    │
    └─► DataVersionManager.create_snapshot(local_data)
            │
            └─► Creates data_versions/2025-11-30_143022.json
                (This file should be committed to Git)
```

---

## 🧪 Test Cases

### File: `tests/test_storage.py`

```python
"""Tests for storage layer."""

import pytest
import json
from pathlib import Path
from datetime import datetime

from llm_pricing.storage import StorageConfig, DataVersionManager, LocalStorage
from llm_pricing.types import PricingDatabase, Provider, ProviderTier


@pytest.fixture
def temp_config(tmp_path):
    """Create a config with temporary directories."""
    return StorageConfig(
        local_data_dir=tmp_path / "local",
        data_versions_dir=tmp_path / "data_versions",
    )


@pytest.fixture
def sample_database():
    """Create a sample database for testing."""
    return PricingDatabase(
        version="1.0",
        providers={
            "test_provider": Provider(
                provider_id="test_provider",
                name="Test Provider",
                tiers={"free": ProviderTier(tier_id="free", name="Free")},
            )
        }
    )


class TestDataVersionManager:
    """Tests for DataVersionManager."""
    
    def test_list_versions_empty(self, temp_config):
        """Test listing versions when directory is empty."""
        manager = DataVersionManager(temp_config)
        assert manager.list_versions() == []
    
    def test_create_and_list_snapshot(self, temp_config, sample_database):
        """Test creating and listing snapshots."""
        manager = DataVersionManager(temp_config)
        
        # Create snapshot
        path = manager.create_snapshot(sample_database)
        assert path.exists()
        assert path.suffix == ".json"
        
        # List versions
        versions = manager.list_versions()
        assert len(versions) == 1
        assert versions[0] == path
    
    def test_load_latest(self, temp_config, sample_database):
        """Test loading latest version."""
        manager = DataVersionManager(temp_config)
        
        # Create snapshot
        manager.create_snapshot(sample_database)
        
        # Load latest
        loaded = manager.load_latest()
        assert loaded is not None
        assert loaded.providers["test_provider"].name == "Test Provider"
    
    def test_get_latest_version_none(self, temp_config):
        """Test get_latest_version when no versions exist."""
        manager = DataVersionManager(temp_config)
        assert manager.get_latest_version() is None
    
    def test_create_multiple_snapshots(self, temp_config, sample_database):
        """Test creating multiple snapshots."""
        manager = DataVersionManager(temp_config)
        
        # Create multiple snapshots
        path1 = manager.create_snapshot(sample_database)
        path2 = manager.create_snapshot(sample_database)
        
        assert path1 != path2
        versions = manager.list_versions()
        assert len(versions) == 2


class TestLocalStorage:
    """Tests for LocalStorage."""
    
    def test_exists_when_empty(self, temp_config):
        """Test exists() when no file."""
        storage = LocalStorage(temp_config)
        assert not storage.exists()
    
    def test_save_and_load(self, temp_config, sample_database):
        """Test saving and loading data."""
        storage = LocalStorage(temp_config)
        
        # Save
        storage.save(sample_database)
        assert storage.exists()
        
        # Load
        loaded = storage.load()
        assert loaded is not None
        assert loaded.providers["test_provider"].name == "Test Provider"
    
    def test_load_when_empty(self, temp_config):
        """Test load() when no file exists."""
        storage = LocalStorage(temp_config)
        assert storage.load() is None
    
    def test_delete(self, temp_config, sample_database):
        """Test deleting local data."""
        storage = LocalStorage(temp_config)
        
        storage.save(sample_database)
        assert storage.exists()
        
        result = storage.delete()
        assert result is True
        assert not storage.exists()
    
    def test_delete_nonexistent(self, temp_config):
        """Test deleting when file doesn't exist."""
        storage = LocalStorage(temp_config)
        result = storage.delete()
        assert result is False
```

---

## ✅ Checklist

### 2.1 Storage Configuration
- [ ] Create `storage/config.py`
- [ ] Implement `StorageConfig` dataclass
- [ ] Auto-detect package `data_versions/` directory
- [ ] Support custom paths

### 2.2 Data Version Manager
- [ ] Create `storage/data_versions.py`
- [ ] Implement `list_versions()` - list all snapshots
- [ ] Implement `get_latest_version()` - get newest snapshot
- [ ] Implement `load_version()` - load specific version
- [ ] Implement `load_latest()` - load newest version
- [ ] Implement `create_snapshot()` - save new snapshot
- [ ] Implement `get_version_info()` - version metadata
- [ ] Write unit tests

### 2.3 Local Storage
- [ ] Create `storage/local_storage.py`
- [ ] Implement `exists()` - check if local data exists
- [ ] Implement `load()` - load local data
- [ ] Implement `save()` - save local data
- [ ] Implement `delete()` - delete local data
- [ ] Write unit tests

### 2.4 Exception Handling
- [ ] Create `exceptions.py`
- [ ] Define `StorageError`
- [ ] Define `StorageNotFoundError`

### 2.5 Package Setup
- [ ] Create `storage/__init__.py`
- [ ] Export all public classes

---

## 📈 Dependencies

- **Phase 1** - Data Models (PricingDatabase, Provider, etc.)

## ➡️ Next Phase

After completing the Storage Layer, proceed to **[PHASE_3_REPOSITORY.md](./PHASE_3_REPOSITORY.md)** for the data access layer.
