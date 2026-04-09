"""Simplified repository for pricing data access."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .storage import LocalStorage, DataVersionManager, StorageConfig
from .exceptions import ValidationError

if TYPE_CHECKING:
    from .models import PricingDatabase, Provider, ModelInfo
else:
    # Runtime imports
    from .models import PricingDatabase, Provider, ModelInfo


class PricingRepository:
    """Repository for accessing and modifying pricing data.

    Provides simplified operations:
    - list_providers(): Get all providers
    - list_models(): Get all models (optionally filtered by provider)
    - get_model(): Get specific model for pricing calculation
    - add_provider(): Add a new provider
    - add_model(): Add a new model

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
            local_storage: LocalStorage instance for user's working data
            version_manager: DataVersionManager instance for bundled snapshots
        """
        self._local_storage = local_storage
        self._version_manager = version_manager
        self._data: Optional[PricingDatabase] = None

    def _ensure_loaded(self) -> PricingDatabase:
        """Ensure data is loaded, initialize if needed."""
        if self._data is None:
            self._data = self._load_or_initialize()
        return self._data

    def _load_or_initialize(self) -> PricingDatabase:
        """Load from local storage, latest snapshot, or create empty database.

        Priority:
        1. Load from local data.json if it exists
        2. Load from latest snapshot in data_versions/ if data.json doesn't exist
        3. Create empty database if no local data or snapshots exist

        This ensures:
        - Persistent local working data is preserved
        - Fresh clones can bootstrap from latest snapshot
        - New installations start with empty database if no snapshots available
        """
        # Try to load from local storage first
        local_data = self._local_storage.load()
        if local_data is not None:
            return local_data

        # No local data - try to load from latest snapshot
        latest_snapshot = self._version_manager.load_latest()
        if latest_snapshot is not None:
            # Save the loaded snapshot as the new local data
            self._local_storage.save(latest_snapshot)
            return latest_snapshot

        # No local data or snapshots - create empty database
        data = PricingDatabase(version="1.0", last_sync=None, providers={})
        self._local_storage.save(data)
        return data

    def list_providers(self) -> dict[str, Provider]:
        """Get all providers.

        Returns:
            Dictionary mapping provider ID to Provider object
        """
        data = self._ensure_loaded()
        return dict(data.providers)

    def list_models(self, provider_id: Optional[str] = None) -> list[ModelInfo]:
        """Get all models, optionally filtered by provider.

        Args:
            provider_id: Optional provider ID to filter by. If None, returns all models.

        Returns:
            List of ModelInfo objects

        Raises:
            ValidationError: If provider_id is specified but doesn't exist
        """
        data = self._ensure_loaded()

        if provider_id is not None:
            if provider_id not in data.providers:
                raise ValidationError(f"Provider '{provider_id}' not found")
            provider = data.providers[provider_id]
            return list(provider.models.values())

        # Return all models from all providers
        all_models = []
        for provider in data.providers.values():
            all_models.extend(provider.models.values())
        return all_models

    def get_model(self, provider_id: str, model_id: str) -> Optional[ModelInfo]:
        """Get specific model for pricing calculation.

        Args:
            provider_id: Provider ID
            model_id: Model ID

        Returns:
            ModelInfo object if found, None otherwise
        """
        data = self._ensure_loaded()

        if provider_id not in data.providers:
            return None

        provider = data.providers[provider_id]
        return provider.models.get(model_id)

    def add_provider(self, provider: Provider) -> None:
        """Add a new provider.

        Args:
            provider: Provider object to add

        Raises:
            ValidationError: If provider with same ID already exists
        """
        data = self._ensure_loaded()

        if provider.provider_id in data.providers:
            raise ValidationError(f"Provider '{provider.provider_id}' already exists")

        data.providers[provider.provider_id] = provider
        self._local_storage.save(data)

    def add_model(self, provider_id: str, model: ModelInfo) -> None:
        """Add a new model to a provider.

        Args:
            provider_id: ID of the provider
            model: ModelInfo object to add

        Raises:
            ValidationError: If provider doesn't exist or model already exists
        """
        data = self._ensure_loaded()

        if provider_id not in data.providers:
            raise ValidationError(f"Provider '{provider_id}' not found")

        provider = data.providers[provider_id]

        if model.model_id in provider.models:
            raise ValidationError(
                f"Model '{model.model_id}' already exists in provider '{provider_id}'"
            )

        provider.models[model.model_id] = model
        self._local_storage.save(data)

    def delete_provider(self, provider_id: str) -> None:
        """Delete a provider and all its models.

        Args:
            provider_id: ID of the provider to delete

        Raises:
            ValidationError: If provider doesn't exist
        """
        data = self._ensure_loaded()

        if provider_id not in data.providers:
            raise ValidationError(f"Provider '{provider_id}' not found")

        del data.providers[provider_id]
        self._local_storage.save(data)

    def delete_model(self, provider_id: str, model_id: str) -> None:
        """Delete a model from a provider.

        Args:
            provider_id: ID of the provider
            model_id: ID of the model to delete

        Raises:
            ValidationError: If provider doesn't exist or model not found
        """
        data = self._ensure_loaded()

        if provider_id not in data.providers:
            raise ValidationError(f"Provider '{provider_id}' not found")

        provider = data.providers[provider_id]

        if model_id not in provider.models:
            raise ValidationError(f"Model '{model_id}' not found in provider '{provider_id}'")

        del provider.models[model_id]
        self._local_storage.save(data)

    @property
    def database(self) -> PricingDatabase:
        """Get the current pricing database.

        Returns:
            The current PricingDatabase instance
        """
        return self._ensure_loaded()

    @property
    def provider_count(self) -> int:
        """Get number of providers."""
        data = self._ensure_loaded()
        return len(data.providers)

    @property
    def model_count(self) -> int:
        """Get total number of models across all providers."""
        data = self._ensure_loaded()
        total = sum(len(p.models) for p in data.providers.values())
        return total


def create_repository(
    local_path: Optional[Path] = None,
    package_root: Optional[Path] = None,
) -> PricingRepository:
    """Factory function to create a repository with default configuration.

    Args:
        local_path: Optional path to local data directory. Defaults to project root
        package_root: Optional path to package root. Auto-detected if not provided.

    Returns:
        Configured PricingRepository instance
    """
    # Use defaults from StorageConfig if not provided
    kwargs = {}
    if local_path is not None:
        kwargs["local_data_dir"] = local_path
    if package_root is not None:
        kwargs["data_versions_dir"] = package_root

    config = StorageConfig(**kwargs)
    config.ensure_local_dir()

    local_storage = LocalStorage(config)
    version_manager = DataVersionManager(config)

    return PricingRepository(local_storage, version_manager)
