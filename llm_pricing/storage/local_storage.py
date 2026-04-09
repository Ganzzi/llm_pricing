"""Local storage for user's working data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..models import PricingDatabase
from ..exceptions import StorageError
from .config import StorageConfig


class LocalStorage:
    """
    Manages user's local working data.

    Location: ~/.llm_pricing/data.json

    This is where runtime modifications are stored. Modifications made via:
    - add_provider()
    - add_model()
    - store_snapshot()

    are persisted here.

    Args:
        config: StorageConfig instance with directory paths
    """

    def __init__(self, config: StorageConfig):
        """Initialize local storage with config."""
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
        Load local data file if it exists.

        Returns:
            Parsed PricingDatabase, or None if file doesn't exist

        Raises:
            StorageError: If file exists but cannot be read or is invalid
        """
        if not self.exists():
            return None

        try:
            with open(self.data_file, "r") as f:
                data = json.load(f)
            return PricingDatabase.model_validate(data)
        except json.JSONDecodeError as e:
            raise StorageError(f"Invalid JSON in local data file {self.data_file}: {e}")
        except Exception as e:
            raise StorageError(f"Failed to load local data from {self.data_file}: {e}")

    def save(self, database: PricingDatabase) -> None:
        """
        Save local data file.

        Creates the directory if needed and writes the database as JSON.

        Args:
            database: PricingDatabase to save

        Raises:
            StorageError: If file cannot be written
        """
        try:
            # Ensure directory exists
            self._config.ensure_local_dir()

            # Serialize database to JSON
            data = json.loads(database.model_dump_json())

            # Write to file
            with open(self.data_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            raise StorageError(f"Failed to save local data to {self.data_file}: {e}")

    def delete(self) -> bool:
        """
        Delete the local data file.

        Returns:
            True if file was deleted, False if file didn't exist
        """
        if self.exists():
            try:
                self.data_file.unlink()
                return True
            except Exception:
                return False
        return False
