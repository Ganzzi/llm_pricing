"""Storage configuration for data locations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StorageConfig:
    """
    Configuration for storage locations.

    Manages paths for:
    - Local working data: <project_root>/data.json (git-ignored)
    - Bundled data versions: <project_root>/data_versions/*.json (git-tracked snapshots)

    Attributes:
        local_data_dir: Directory for local data (default: project root)
        data_versions_dir: Directory for bundled snapshots (auto-detected from project root)
    """

    # Local data directory (defaults to project root)
    local_data_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)

    # Data versions directory (relative to project root)
    data_versions_dir: Path | None = field(default=None)

    @property
    def local_data_file(self) -> Path:
        """Path to user's working data file."""
        return self.local_data_dir / "data.json"

    def get_data_versions_dir(self) -> Path:
        """
        Get the data_versions directory (at project root).

        Auto-detects if not explicitly set:
        - Looks for <project_root>/data_versions/
        - Where project_root is determined by this file's location

        Returns:
            Path to data_versions directory
        """
        if self.data_versions_dir:
            return self.data_versions_dir

        # Auto-detect: project root / data_versions
        # This file is at: llm_pricing/storage/config.py
        # Project root is: up 3 levels
        project_root = Path(__file__).parent.parent.parent
        return project_root / "data_versions"

    def ensure_local_dir(self) -> None:
        """Ensure local data directory exists."""
        self.local_data_dir.mkdir(parents=True, exist_ok=True)

    def ensure_data_versions_dir(self) -> None:
        """Ensure data versions directory exists."""
        versions_dir = self.get_data_versions_dir()
        versions_dir.mkdir(parents=True, exist_ok=True)
