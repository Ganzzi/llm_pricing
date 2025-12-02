"""Snapshot management for storing data versions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .models import PricingDatabase
from .exceptions import StorageError

if TYPE_CHECKING:
    from .repository import PricingRepository
    from .storage import DataVersionManager


@dataclass
class SnapshotInfo:
    """Information about a pricing data snapshot.

    Attributes:
        filename: Name of the snapshot file (e.g., '2025-01-15_120000_000000.json')
        path: Full path to the snapshot file
        timestamp: When the snapshot was created
        provider_count: Number of providers in the snapshot
        model_count: Total number of models in the snapshot
    """

    filename: str
    path: Path
    timestamp: datetime
    provider_count: int
    model_count: int


class SnapshotManager:
    """Manager for creating and listing pricing data snapshots.

    Snapshots are JSON files saved to the data_versions folder with
    datetime-based naming (e.g., 2025-01-15_120000_000000.json).

    This allows users to persist their custom pricing data as versioned
    snapshots that can be bundled with the package for distribution.

    Args:
        repository: Repository for accessing current data
        version_manager: Manager for data versions storage
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
            Created: 2025-01-15_143022_000000.json
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Get current database from repository
        database = self._repo.database

        # Directly save snapshot file with the provided timestamp
        snapshot_path = self._save_snapshot_file(database, timestamp)

        # Calculate stats
        provider_count = len(database.providers)
        model_count = sum(len(p.models) for p in database.providers.values())

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

        for snapshot_path in self._versions.list_versions():
            try:
                timestamp = self._parse_filename_timestamp(snapshot_path.name)
                database = self._versions.load_version(snapshot_path)

                provider_count = len(database.providers)
                model_count = sum(len(p.models) for p in database.providers.values())

                snapshots.append(
                    SnapshotInfo(
                        filename=snapshot_path.name,
                        path=snapshot_path,
                        timestamp=timestamp,
                        provider_count=provider_count,
                        model_count=model_count,
                    )
                )
            except (ValueError, Exception):
                # Skip invalid snapshot files
                continue

        # Already sorted newest first by list_versions()
        return snapshots

    def get_snapshot_info(self, filename: str) -> Optional[SnapshotInfo]:
        """Get information about a specific snapshot.

        Args:
            filename: Snapshot filename (e.g., '2025-01-15_120000_000000.json')

        Returns:
            SnapshotInfo if found, None otherwise
        """
        available = self._versions.list_versions()
        snapshot_path = None

        for path in available:
            if path.name == filename:
                snapshot_path = path
                break

        if snapshot_path is None:
            return None

        try:
            timestamp = self._parse_filename_timestamp(filename)
            database = self._versions.load_version(snapshot_path)

            provider_count = len(database.providers)
            model_count = sum(len(p.models) for p in database.providers.values())

            return SnapshotInfo(
                filename=filename,
                path=snapshot_path,
                timestamp=timestamp,
                provider_count=provider_count,
                model_count=model_count,
            )
        except Exception:
            return None

    def _save_snapshot_file(
        self,
        database: PricingDatabase,
        timestamp: datetime,
    ) -> Path:
        """Save snapshot file directly with given timestamp.

        Args:
            database: Database to save
            timestamp: Timestamp to use for filename

        Returns:
            Path to created file

        Raises:
            StorageError: If save fails
        """
        # Ensure data versions directory exists
        versions_dir = self._versions.versions_dir
        versions_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        filename = timestamp.strftime("%Y-%m-%d_%H%M%S_%f.json")
        snapshot_path = versions_dir / filename

        try:
            # Serialize database to JSON
            data = json.loads(database.model_dump_json())

            # Write to file
            with open(snapshot_path, "w") as f:
                json.dump(data, f, indent=2, default=str)

            return snapshot_path
        except Exception as e:
            raise StorageError(f"Failed to create snapshot {snapshot_path}: {e}")

    @staticmethod
    def _parse_filename_timestamp(filename: str) -> datetime:
        """Parse timestamp from snapshot filename.

        Args:
            filename: Filename like '2025-01-15_120000_000000.json'

        Returns:
            Parsed datetime

        Raises:
            ValueError: If filename format is invalid
        """
        # Remove .json extension
        name = filename.replace(".json", "")
        # Parse: YYYY-MM-DD_HHMMSS_ffffff
        return datetime.strptime(name, "%Y-%m-%d_%H%M%S_%f")


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

    Example:
        >>> from llm_pricing.snapshot import create_snapshot_manager
        >>> manager = create_snapshot_manager(repo, version_manager)
        >>> info = manager.create_snapshot()
    """
    return SnapshotManager(repository, version_manager)
