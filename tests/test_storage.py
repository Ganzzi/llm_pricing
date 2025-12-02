"""Tests for storage layer."""

import pytest
import json
from pathlib import Path
from datetime import datetime

from llm_pricing.storage import StorageConfig, DataVersionManager, LocalStorage
from llm_pricing.models import PricingDatabase, Provider, ProviderTier, ModelInfo


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
                tiers={
                    "default": ProviderTier(
                        tier_id="default",
                        name="Default",
                    )
                },
                models={
                    "test_model": ModelInfo(
                        model_id="test_model",
                        name="Test Model",
                        provider_id="test_provider",
                        pricing={
                            "input_mtok": 1.0,
                            "output_mtok": 2.0,
                        },
                    )
                },
            )
        },
    )


class TestStorageConfig:
    """Tests for StorageConfig."""

    def test_default_local_data_dir(self):
        """Test default local data directory is project root."""
        config = StorageConfig()
        # Default should be project root (not home directory)
        # Project root is 2 levels up from tests/test_storage.py
        expected = Path(__file__).parent.parent
        assert config.local_data_dir == expected

    def test_custom_local_data_dir(self, tmp_path):
        """Test custom local data directory."""
        custom_dir = tmp_path / "custom"
        config = StorageConfig(local_data_dir=custom_dir)
        assert config.local_data_dir == custom_dir

    def test_local_data_file_path(self, tmp_path):
        """Test local data file path property."""
        config = StorageConfig(local_data_dir=tmp_path)
        assert config.local_data_file == tmp_path / "data.json"

    def test_get_data_versions_dir_explicit(self, tmp_path):
        """Test explicit data versions directory."""
        versions_dir = tmp_path / "versions"
        config = StorageConfig(data_versions_dir=versions_dir)
        assert config.get_data_versions_dir() == versions_dir

    def test_get_data_versions_dir_auto_detect(self, tmp_path):
        """Test auto-detection of data versions directory."""
        config = StorageConfig(local_data_dir=tmp_path)
        versions_dir = config.get_data_versions_dir()
        # Should point to package's data_versions directory
        assert "data_versions" in str(versions_dir)

    def test_ensure_local_dir(self, tmp_path):
        """Test ensuring local directory exists."""
        local_dir = tmp_path / "new_dir"
        config = StorageConfig(local_data_dir=local_dir)
        assert not local_dir.exists()
        config.ensure_local_dir()
        assert local_dir.exists()

    def test_ensure_data_versions_dir(self, tmp_path):
        """Test ensuring data versions directory exists."""
        versions_dir = tmp_path / "new_versions"
        config = StorageConfig(data_versions_dir=versions_dir)
        assert not versions_dir.exists()
        config.ensure_data_versions_dir()
        assert versions_dir.exists()


class TestDataVersionManager:
    """Tests for DataVersionManager."""

    def test_init(self, temp_config):
        """Test initialization."""
        manager = DataVersionManager(temp_config)
        assert manager.versions_dir == temp_config.get_data_versions_dir()

    def test_list_versions_empty(self, temp_config):
        """Test listing versions when directory is empty."""
        manager = DataVersionManager(temp_config)
        assert manager.list_versions() == []

    def test_list_versions_sorted(self, temp_config, sample_database):
        """Test listing versions returns newest first."""
        import time

        manager = DataVersionManager(temp_config)
        temp_config.ensure_data_versions_dir()

        # Create multiple versions with delay to ensure distinct timestamps
        path1 = manager.create_snapshot(sample_database)
        time.sleep(0.01)  # 10ms delay to avoid timestamp collision
        path2 = manager.create_snapshot(sample_database)
        time.sleep(0.01)
        path3 = manager.create_snapshot(sample_database)

        versions = manager.list_versions()
        assert len(versions) == 3
        # Newest first
        assert versions[0] == path3
        assert versions[1] == path2
        assert versions[2] == path1

    def test_get_latest_version_none(self, temp_config):
        """Test get_latest_version when no versions exist."""
        manager = DataVersionManager(temp_config)
        assert manager.get_latest_version() is None

    def test_get_latest_version(self, temp_config, sample_database):
        """Test get_latest_version returns newest."""
        import time

        manager = DataVersionManager(temp_config)
        path1 = manager.create_snapshot(sample_database)
        time.sleep(0.01)  # Avoid timestamp collision
        path2 = manager.create_snapshot(sample_database)

        latest = manager.get_latest_version()
        assert latest == path2
        assert latest != path1

    def test_load_version(self, temp_config, sample_database):
        """Test loading a specific version."""
        manager = DataVersionManager(temp_config)
        path = manager.create_snapshot(sample_database)

        loaded = manager.load_version(path)
        assert isinstance(loaded, PricingDatabase)
        assert loaded.version == "1.0"
        assert "test_provider" in loaded.providers

    def test_load_version_not_found(self, temp_config):
        """Test loading non-existent version."""
        manager = DataVersionManager(temp_config)
        with pytest.raises(Exception):  # StorageNotFoundError
            manager.load_version(Path("nonexistent.json"))

    def test_load_latest(self, temp_config, sample_database):
        """Test loading latest version."""
        manager = DataVersionManager(temp_config)
        manager.create_snapshot(sample_database)

        loaded = manager.load_latest()
        assert isinstance(loaded, PricingDatabase)
        assert loaded.version == "1.0"
        assert "test_provider" in loaded.providers

    def test_load_latest_none(self, temp_config):
        """Test load_latest when no versions exist."""
        manager = DataVersionManager(temp_config)
        assert manager.load_latest() is None

    def test_create_snapshot(self, temp_config, sample_database):
        """Test creating a snapshot."""
        manager = DataVersionManager(temp_config)
        path = manager.create_snapshot(sample_database)

        assert path.exists()
        assert path.suffix == ".json"
        assert path.parent == temp_config.get_data_versions_dir()

    def test_create_snapshot_filename_format(self, temp_config, sample_database):
        """Test snapshot filename uses correct format."""
        manager = DataVersionManager(temp_config)
        path = manager.create_snapshot(sample_database)

        # Format: YYYY-MM-DD_HHMMSS_ffffff.json
        name = path.name
        # Example: 2025-11-30_181156_564427.json (29 chars)
        assert len(name) == 29
        assert name[4] == "-"  # Year separator
        assert name[7] == "-"  # Month separator
        assert name[10] == "_"  # Date-time separator
        assert name[17] == "_"  # Seconds-microseconds separator
        assert name.endswith(".json")

    def test_create_snapshot_dir_created(self, temp_config, sample_database):
        """Test that directory is created if needed."""
        manager = DataVersionManager(temp_config)
        versions_dir = temp_config.get_data_versions_dir()
        assert not versions_dir.exists()

        manager.create_snapshot(sample_database)
        assert versions_dir.exists()

    def test_get_version_info(self, temp_config, sample_database):
        """Test getting version info."""
        manager = DataVersionManager(temp_config)
        path = manager.create_snapshot(sample_database)

        info = manager.get_version_info(path)
        assert info["filename"] == path.name
        assert info["size_bytes"] > 0
        assert info["num_providers"] == 1

    def test_snapshot_roundtrip(self, temp_config, sample_database):
        """Test saving and loading a snapshot."""
        manager = DataVersionManager(temp_config)
        path = manager.create_snapshot(sample_database)
        loaded = manager.load_version(path)

        assert loaded.providers["test_provider"].name == "Test Provider"
        assert "test_model" in loaded.providers["test_provider"].models


class TestLocalStorage:
    """Tests for LocalStorage."""

    def test_init(self, temp_config):
        """Test initialization."""
        storage = LocalStorage(temp_config)
        assert storage.data_file == temp_config.local_data_file

    def test_exists_when_empty(self, temp_config):
        """Test exists() when no file."""
        storage = LocalStorage(temp_config)
        assert not storage.exists()

    def test_save_and_load(self, temp_config, sample_database):
        """Test saving and loading data."""
        storage = LocalStorage(temp_config)
        storage.save(sample_database)

        assert storage.exists()
        loaded = storage.load()
        assert loaded is not None
        assert loaded.providers["test_provider"].name == "Test Provider"

    def test_load_when_empty(self, temp_config):
        """Test load() when no file exists."""
        storage = LocalStorage(temp_config)
        assert storage.load() is None

    def test_save_creates_dir(self, temp_config, sample_database):
        """Test that save() creates directory if needed."""
        storage = LocalStorage(temp_config)
        assert not temp_config.local_data_dir.exists()

        storage.save(sample_database)
        assert temp_config.local_data_dir.exists()

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

    def test_save_overwrites(self, temp_config, sample_database):
        """Test that save() overwrites existing file."""
        storage = LocalStorage(temp_config)
        storage.save(sample_database)
        first_size = storage.data_file.stat().st_size

        # Save again - should succeed
        storage.save(sample_database)
        second_size = storage.data_file.stat().st_size
        assert first_size == second_size

    def test_roundtrip_preserves_data(self, temp_config, sample_database):
        """Test that data is preserved through save/load cycle."""
        storage = LocalStorage(temp_config)
        storage.save(sample_database)
        loaded = storage.load()

        assert loaded.version == sample_database.version
        assert len(loaded.providers) == len(sample_database.providers)
        assert loaded.providers["test_provider"].provider_id == "test_provider"
