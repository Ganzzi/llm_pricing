"""Data version management - bundled snapshots shipped with package."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import PricingDatabase
from ..exceptions import StorageError, StorageNotFoundError
from .config import StorageConfig


class DataVersionManager:
    """
    Manages data version snapshots bundled with the package.

    Snapshots are stored in `data_versions/` folder at the package root.
    Files are named with datetime: YYYY-MM-DD_HHMMSS_ffffff.json (includes microseconds)

    These files are:
    - Git tracked (committed to repository)
    - Shipped with the package
    - Read-only during normal use
    - Created via store_snapshot() from local data

    Args:
        config: StorageConfig instance with directory paths
    """

    FILENAME_FORMAT = "%Y-%m-%d_%H%M%S_%f.json"

    def __init__(self, config: StorageConfig):
        """Initialize manager with storage config."""
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
        Load a specific data version file.

        Args:
            version_path: Path to the version file to load

        Returns:
            Parsed PricingDatabase

        Raises:
            StorageNotFoundError: If version file doesn't exist
            StorageError: If file cannot be read or is invalid JSON
        """
        if not version_path.exists():
            raise StorageNotFoundError(f"Data version file not found: {version_path}")

        try:
            with open(version_path, "r") as f:
                data = json.load(f)
            return PricingDatabase.model_validate(data)
        except json.JSONDecodeError as e:
            raise StorageError(f"Invalid JSON in data version file {version_path}: {e}")
        except Exception as e:
            raise StorageError(f"Failed to load data version {version_path}: {e}")

    def load_latest(self) -> Optional[PricingDatabase]:
        """
        Load the latest data version file.

        Returns:
            Parsed PricingDatabase from latest version, or None if no versions exist
        """
        latest = self.get_latest_version()
        if latest is None:
            return None
        return self.load_version(latest)

    def create_snapshot(self, database: PricingDatabase) -> Path:
        """
        Create a new snapshot file from a PricingDatabase.

        Saves the database to a new file in data_versions/ directory
        with a datetime-based filename: YYYY-MM-DD_HHMMSS.json

        Args:
            database: PricingDatabase to save

        Returns:
            Path to the created snapshot file

        Raises:
            StorageError: If snapshot cannot be created
        """
        # Ensure directory exists
        self._config.ensure_data_versions_dir()

        # Generate filename with current datetime
        timestamp = datetime.now()
        filename = timestamp.strftime(self.FILENAME_FORMAT)
        snapshot_path = self._versions_dir / filename

        try:
            # Serialize database to JSON
            data = json.loads(database.model_dump_json())

            # Write to file
            with open(snapshot_path, "w") as f:
                json.dump(data, f, indent=2, default=str)

            return snapshot_path
        except Exception as e:
            raise StorageError(f"Failed to create snapshot {snapshot_path}: {e}")

    def get_version_info(self, version_path: Path) -> dict:
        """
        Get metadata information about a data version file.

        Args:
            version_path: Path to the version file

        Returns:
            Dictionary with version metadata:
            - path: str - Full path to file
            - filename: str - Filename only
            - size_bytes: int - File size
            - created_at: str - File creation time
            - num_providers: int - Number of providers in database

        Raises:
            StorageError: If version cannot be read
        """
        if not version_path.exists():
            raise StorageError(f"Version file not found: {version_path}")

        try:
            stat = version_path.stat()
            database = self.load_version(version_path)

            return {
                "path": str(version_path),
                "filename": version_path.name,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "num_providers": len(database.providers),
            }
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to get version info: {e}")
