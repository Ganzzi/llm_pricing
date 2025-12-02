"""Tests for snapshot management functionality."""

import pytest
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from tempfile import TemporaryDirectory

from llm_pricing.snapshot import SnapshotManager, SnapshotInfo, create_snapshot_manager
from llm_pricing.models import (
    PricingDatabase,
    Provider,
    ProviderTier,
    ModelInfo,
    ModelPrice,
)
from llm_pricing.storage import LocalStorage, DataVersionManager, StorageConfig
from llm_pricing.repository import PricingRepository


@pytest.fixture
def temp_storage():
    """Create temporary storage directories."""
    with TemporaryDirectory() as tmpdir:
        local_dir = Path(tmpdir) / "local"
        versions_dir = Path(tmpdir) / "versions"
        local_dir.mkdir()
        versions_dir.mkdir()

        config = StorageConfig(
            local_data_dir=local_dir,
            data_versions_dir=versions_dir,
        )

        yield {
            "config": config,
            "local_storage": LocalStorage(config),
            "version_manager": DataVersionManager(config),
        }


@pytest.fixture
def sample_database():
    """Create a sample database for testing."""
    return PricingDatabase(
        version="1.0.0",
        last_sync=None,
        providers={
            "anthropic": Provider(
                provider_id="anthropic",
                name="Anthropic",
                tiers={},
                models={
                    "claude-sonnet": ModelInfo(
                        model_id="claude-sonnet",
                        name="Claude Sonnet",
                        provider_id="anthropic",
                        pricing=ModelPrice(
                            input_mtok=Decimal("3.0"),
                            output_mtok=Decimal("15.0"),
                        ),
                        rate_limiters={},
                    ),
                    "claude-opus": ModelInfo(
                        model_id="claude-opus",
                        name="Claude Opus",
                        provider_id="anthropic",
                        pricing=ModelPrice(
                            input_mtok=Decimal("15.0"),
                            output_mtok=Decimal("75.0"),
                        ),
                        rate_limiters={},
                    ),
                },
            ),
            "openai": Provider(
                provider_id="openai",
                name="OpenAI",
                tiers={},
                models={
                    "gpt-4": ModelInfo(
                        model_id="gpt-4",
                        name="GPT-4",
                        provider_id="openai",
                        pricing=ModelPrice(
                            input_mtok=Decimal("30.0"),
                            output_mtok=Decimal("60.0"),
                        ),
                        rate_limiters={},
                    ),
                },
            ),
        },
    )


@pytest.fixture
def manager(temp_storage, sample_database):
    """Create snapshot manager with sample data."""
    # Initialize local storage with sample data
    temp_storage["local_storage"].save(sample_database)

    # Create repository
    repo = PricingRepository(
        temp_storage["local_storage"],
        temp_storage["version_manager"],
    )

    # Create and return snapshot manager
    return SnapshotManager(repo, temp_storage["version_manager"])


class TestSnapshotInfo:
    """Tests for SnapshotInfo dataclass."""

    def test_snapshot_info_creation(self):
        """Test creating SnapshotInfo instance."""
        info = SnapshotInfo(
            filename="2025-01-15_120000_000000.json",
            path=Path("/some/path/2025-01-15_120000_000000.json"),
            timestamp=datetime(2025, 1, 15, 12, 0, 0),
            provider_count=2,
            model_count=5,
        )

        assert info.filename == "2025-01-15_120000_000000.json"
        assert info.provider_count == 2
        assert info.model_count == 5

    def test_snapshot_info_attributes(self):
        """Test all attributes of SnapshotInfo."""
        path = Path("/test/path/snapshot.json")
        ts = datetime(2025, 1, 15, 12, 30, 45, 123456)

        info = SnapshotInfo(
            filename="snapshot.json",
            path=path,
            timestamp=ts,
            provider_count=10,
            model_count=100,
        )

        assert info.path == path
        assert info.timestamp == ts


class TestSnapshotManagerCreateSnapshot:
    """Tests for SnapshotManager.create_snapshot()."""

    def test_create_snapshot_creates_file(self, manager):
        """Test that create_snapshot creates a new file."""
        info = manager.create_snapshot()

        assert info.path.exists()
        assert info.filename.endswith(".json")

    def test_create_snapshot_default_timestamp(self, manager):
        """Test that create_snapshot uses current timestamp by default."""
        before = datetime.now()
        info = manager.create_snapshot()
        after = datetime.now()

        # Timestamp should be between before and after
        assert before <= info.timestamp <= after

    def test_create_snapshot_custom_timestamp(self, manager):
        """Test that create_snapshot respects custom timestamp."""
        custom_ts = datetime(2025, 1, 15, 12, 30, 45, 123456)
        info = manager.create_snapshot(timestamp=custom_ts)

        assert info.timestamp == custom_ts
        assert info.filename == "2025-01-15_123045_123456.json"

    def test_create_snapshot_correct_stats(self, manager):
        """Test that snapshot info has correct statistics."""
        info = manager.create_snapshot()

        # Sample data has 2 providers and 3 models
        assert info.provider_count == 2
        assert info.model_count == 3

    def test_create_snapshot_contains_valid_data(self, manager):
        """Test that created snapshot contains valid JSON with correct data."""
        info = manager.create_snapshot()

        # Load and verify
        data = PricingDatabase.model_validate_json(info.path.read_text())
        assert "anthropic" in data.providers
        assert "openai" in data.providers
        assert "claude-sonnet" in data.providers["anthropic"].models
        assert "gpt-4" in data.providers["openai"].models

    def test_create_snapshot_returns_snapshot_info(self, manager):
        """Test that create_snapshot returns SnapshotInfo object."""
        result = manager.create_snapshot()

        assert isinstance(result, SnapshotInfo)
        assert result.filename
        assert result.path
        assert result.timestamp
        assert result.provider_count >= 0
        assert result.model_count >= 0

    def test_create_snapshot_multiple_times(self, manager):
        """Test creating multiple snapshots with different timestamps."""
        ts1 = datetime(2025, 1, 10, 10, 0, 0)
        ts2 = datetime(2025, 1, 15, 15, 0, 0)

        info1 = manager.create_snapshot(timestamp=ts1)
        info2 = manager.create_snapshot(timestamp=ts2)

        assert info1.path != info2.path
        assert info1.filename != info2.filename
        assert info1.timestamp != info2.timestamp
        assert info1.path.exists()
        assert info2.path.exists()


class TestSnapshotManagerListSnapshots:
    """Tests for SnapshotManager.list_snapshots()."""

    def test_list_snapshots_after_create(self, manager):
        """Test listing after creating a snapshot."""
        manager.create_snapshot()

        snapshots = manager.list_snapshots()
        assert len(snapshots) == 1

    def test_list_snapshots_multiple(self, manager):
        """Test listing multiple snapshots."""
        manager.create_snapshot(timestamp=datetime(2025, 1, 10, 10, 0, 0, 100000))
        manager.create_snapshot(timestamp=datetime(2025, 1, 12, 12, 0, 0, 200000))
        manager.create_snapshot(timestamp=datetime(2025, 1, 15, 15, 0, 0, 300000))

        snapshots = manager.list_snapshots()
        assert len(snapshots) == 3

    def test_list_snapshots_sorted_newest_first(self, manager):
        """Test that snapshots are sorted newest first."""
        manager.create_snapshot(timestamp=datetime(2025, 1, 10, 10, 0, 0, 100000))
        manager.create_snapshot(timestamp=datetime(2025, 1, 15, 15, 0, 0, 300000))
        manager.create_snapshot(timestamp=datetime(2025, 1, 12, 12, 0, 0, 200000))

        snapshots = manager.list_snapshots()

        # Verify sorted by timestamp, newest first
        assert snapshots[0].timestamp > snapshots[1].timestamp
        assert snapshots[1].timestamp > snapshots[2].timestamp

    def test_list_snapshots_returns_valid_info(self, manager):
        """Test that listed snapshots contain valid SnapshotInfo."""
        manager.create_snapshot()

        snapshots = manager.list_snapshots()

        for info in snapshots:
            assert isinstance(info, SnapshotInfo)
            assert info.filename.endswith(".json")
            assert info.path.exists()
            assert info.provider_count >= 0
            assert info.model_count >= 0


class TestSnapshotManagerGetSnapshotInfo:
    """Tests for SnapshotManager.get_snapshot_info()."""

    def test_get_snapshot_info_found(self, manager):
        """Test getting info for existing snapshot."""
        created = manager.create_snapshot(timestamp=datetime(2025, 1, 15, 12, 30, 45, 123456))

        info = manager.get_snapshot_info(created.filename)

        assert info is not None
        assert info.filename == created.filename
        assert info.timestamp == created.timestamp

    def test_get_snapshot_info_not_found(self, manager):
        """Test getting info for non-existent snapshot."""
        info = manager.get_snapshot_info("nonexistent.json")

        assert info is None

    def test_get_snapshot_info_invalid_filename(self, manager):
        """Test getting info with invalid filename format."""
        manager.create_snapshot()

        # Try to get non-existent file
        info = manager.get_snapshot_info("invalid_format.json")
        assert info is None

    def test_get_snapshot_info_after_create_multiple(self, manager):
        """Test getting specific snapshot info from multiple."""
        info1 = manager.create_snapshot(timestamp=datetime(2025, 1, 10, 10, 0, 0, 100000))
        info2 = manager.create_snapshot(timestamp=datetime(2025, 1, 15, 15, 0, 0, 300000))

        # Get first one
        retrieved = manager.get_snapshot_info(info1.filename)
        assert retrieved is not None
        assert retrieved.filename == info1.filename
        assert retrieved.timestamp == info1.timestamp

        # Get second one
        retrieved = manager.get_snapshot_info(info2.filename)
        assert retrieved is not None
        assert retrieved.filename == info2.filename
        assert retrieved.timestamp == info2.timestamp


class TestSnapshotManagerTimestampParsing:
    """Tests for timestamp parsing from filenames."""

    def test_parse_filename_timestamp_valid(self, manager):
        """Test parsing valid timestamp from filename."""
        filename = "2025-01-15_123045_123456.json"
        ts = manager._parse_filename_timestamp(filename)

        assert ts.year == 2025
        assert ts.month == 1
        assert ts.day == 15
        assert ts.hour == 12
        assert ts.minute == 30
        assert ts.second == 45
        assert ts.microsecond == 123456

    def test_parse_filename_timestamp_invalid_format(self, manager):
        """Test parsing invalid timestamp format raises error."""
        with pytest.raises(ValueError):
            manager._parse_filename_timestamp("invalid_format.json")

    def test_parse_filename_timestamp_missing_json_extension(self, manager):
        """Test parsing filename without .json extension."""
        filename = "2025-01-15_123045_123456"
        ts = manager._parse_filename_timestamp(filename)

        assert ts.year == 2025
        assert ts.month == 1
        assert ts.day == 15


class TestCreateSnapshotManagerFactory:
    """Tests for create_snapshot_manager factory function."""

    def test_create_snapshot_manager_returns_manager(self, manager):
        """Test that factory returns SnapshotManager instance."""
        result = create_snapshot_manager(manager._repo, manager._versions)

        assert isinstance(result, SnapshotManager)

    def test_create_snapshot_manager_is_functional(self, manager):
        """Test that created manager is functional."""
        # Should be able to create snapshot
        info = manager.create_snapshot()
        assert info is not None
        assert info.path.exists()
