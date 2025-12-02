"""Main LLMPricing class - unified interface for all pricing operations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional
from decimal import Decimal

from .repository import PricingRepository, create_repository
from .engine import PricingEngine, TokenUsage, CostBreakdown
from .snapshot import SnapshotManager, SnapshotInfo, create_snapshot_manager
from .storage import DataVersionManager, StorageConfig

if TYPE_CHECKING:
    from .models import Provider, ModelInfo


class LLMPricing:
    """Main interface for LLM pricing operations.

    This class provides a simple API for:
    - Calculating costs for API usage
    - Listing providers and models
    - Adding and deleting providers and models
    - Storing and managing snapshots

    Data Storage:
    - Local working data is stored at `project_root/data.json` (git-ignored)
    - Snapshots are stored at `project_root/data_versions/` (git-tracked)
    - On first use, auto-loads from latest snapshot if data.json doesn't exist
    - All changes are persisted immediately to data.json

    Workflow:
    1. First run: Creates data.json by loading latest snapshot
    2. Add/modify providers and models as needed
    3. Use store_snapshot() to save reference snapshots
    4. On next run: Loads persisted data.json automatically

    Example:
        ```python
        from llm_pricing import LLMPricing, TokenUsage

        # Initialize
        pricing = LLMPricing()

        # Calculate cost
        usage = TokenUsage(input_tokens=100000, output_tokens=50000)
        result = pricing.calculate(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            usage=usage,
            tier="pro",
        )

        print(f"Total: ${result.total_cost}")

        # List providers
        providers = pricing.list_providers()
        for provider_id, provider in providers.items():
            print(f"{provider_id}: {provider.name}")

        # Store snapshot
        info = pricing.store_naspshot()
        print(f"Saved: {info.filename}")
        ```
    """

    def __init__(
        self,
        local_path: Optional[Path] = None,
        package_root: Optional[Path] = None,
    ):
        """Initialize LLMPricing.

        Args:
            local_path: Optional path to local data directory.
                       Defaults to project root
            package_root: Optional path to package root.
                         Auto-detected if not provided.

        Example:
            ```python
            # Default initialization
            pricing = LLMPricing()

            # Custom local storage path
            pricing = LLMPricing(local_path=Path("/custom/data"))
            ```
        """
        self._repo = create_repository(local_path=local_path, package_root=package_root)
        self._engine = PricingEngine(self._repo)

        # Initialize snapshot manager with proper config
        kwargs = {}
        if local_path is not None:
            kwargs["local_data_dir"] = local_path
        if package_root is not None:
            kwargs["data_versions_dir"] = package_root

        config = StorageConfig(**kwargs)
        version_manager = DataVersionManager(config)
        self._snapshot_manager = create_snapshot_manager(self._repo, version_manager)

    # === Core API Methods ===

    def calculate(
        self,
        usage: TokenUsage,
        provider: str,
        model: str,
        tier: Optional[str] = None,
    ) -> CostBreakdown:
        """Calculate cost for token usage.

        Retrieves model pricing, applies tiered pricing if applicable,
        and returns detailed cost breakdown.

        Args:
            usage: TokenUsage with token counts
            provider: Provider ID (e.g., "anthropic")
            model: Model ID (e.g., "claude-sonnet-4-20250514")
            tier: Optional provider tier (e.g., "pro"). Falls back to "default"

        Returns:
            CostBreakdown with detailed cost information

        Raises:
            ValueError: If provider or model not found

        Example:
            ```python
            from llm_pricing import TokenUsage

            usage = TokenUsage(
                input_tokens=100000,
                output_tokens=50000,
            )
            result = pricing.calculate(
                usage=usage,
                provider="anthropic",
                model="claude-sonnet-4-20250514",
            )
            print(f"Input: ${result.input_cost}")
            print(f"Output: ${result.output_cost}")
            print(f"Total: ${result.total_cost}")
            ```
        """
        return self._engine.calculate(
            provider_id=provider,
            model_id=model,
            usage=usage,
            tier=tier,
        )

    def list_providers(self) -> dict[str, Provider]:
        """Get all providers with their complete data.

        Returns:
            Dictionary mapping provider ID to Provider object.
            Each Provider includes its tiers and models.

        Example:
            ```python
            providers = pricing.list_providers()
            for provider_id, provider in providers.items():
                print(f"{provider_id}: {provider.name}")
                print(f"  Tiers: {len(provider.tiers)}")
                print(f"  Models: {len(provider.models)}")
            ```
        """
        return self._repo.list_providers()

    def list_models(
        self,
        provider: Optional[str] = None,
    ) -> list[ModelInfo]:
        """Get all models, optionally filtered by provider.

        Args:
            provider: Optional provider ID to filter by.
                     If None, returns all models from all providers.

        Returns:
            List of ModelInfo objects

        Raises:
            ValueError: If provider is specified but doesn't exist

        Example:
            ```python
            # All models
            all_models = pricing.list_models()
            print(f"Total models: {len(all_models)}")

            # Anthropic models only
            anthropic_models = pricing.list_models(provider="anthropic")
            for model in anthropic_models:
                print(f"  {model.model_id}")
            ```
        """
        return self._repo.list_models(provider_id=provider)

    def add_provider(self, provider: Provider) -> None:
        """Add a new provider.

        Immediately persists to local storage.

        Args:
            provider: Provider object to add

        Raises:
            ValueError: If provider with same ID already exists

        Example:
            ```python
            from llm_pricing import Provider

            provider = Provider(
                provider_id="my-company",
                name="My Company",
                models={},
            )
            pricing.add_provider(provider)
            ```
        """
        self._repo.add_provider(provider)

    def add_model(
        self,
        provider: str,
        model: ModelInfo,
    ) -> None:
        """Add a new model to a provider.

        Immediately persists to local storage.

        Args:
            provider: Provider ID
            model: ModelInfo object to add

        Raises:
            ValueError: If provider doesn't exist or model already exists

        Example:
            ```python
            from llm_pricing import ModelInfo, ModelPrice

            model = ModelInfo(
                model_id="my-model-v1",
                name="My Model v1",
                pricing={
                    "default": ModelPrice(
                        input_mtok=Decimal("1.00"),
                        output_mtok=Decimal("2.00"),
                    )
                },
            )
            pricing.add_model("my-company", model)
            ```
        """
        self._repo.add_model(provider, model)

    def delete_provider(self, provider_id: str) -> None:
        """Delete a provider and all its models.

        Immediately persists to local storage.

        Args:
            provider_id: ID of the provider to delete

        Raises:
            ValueError: If provider doesn't exist

        Example:
            ```python
            pricing.delete_provider("openai")
            print(f"Providers: {pricing.provider_count}")
            ```
        """
        self._repo.delete_provider(provider_id)

    def delete_model(self, provider_id: str, model_id: str) -> None:
        """Delete a model from a provider.

        Immediately persists to local storage.

        Args:
            provider_id: ID of the provider
            model_id: ID of the model to delete

        Raises:
            ValueError: If provider doesn't exist or model not found

        Example:
            ```python
            pricing.delete_model("openai", "gpt-4o-mini")
            print(f"Total models: {pricing.model_count}")
            ```
        """
        self._repo.delete_model(provider_id, model_id)

    def store_snapshot(self) -> SnapshotInfo:
        """Store current data as a new snapshot.

        Creates a new snapshot file in the data_versions folder with
        datetime-based naming (e.g., 2025-01-15_143022_000000.json).

        Returns:
            SnapshotInfo with details about the created snapshot

        Example:
            ```python
            # Add some custom data
            pricing.add_provider(my_provider)
            pricing.add_model("my-provider", my_model)

            # Store as snapshot
            info = pricing.store_snapshot()
            print(f"Created snapshot: {info.filename}")
            print(f"  Providers: {info.provider_count}")
            print(f"  Models: {info.model_count}")
            ```
        """
        return self._snapshot_manager.create_snapshot()

    def validate(
        self,
        provider: str,
        model: str,
    ) -> bool:
        """Validate that a provider and model exist in local storage.

        Checks if both the provider and model exist and are available
        in the current pricing database.

        Args:
            provider: Provider ID (e.g., "anthropic")
            model: Model ID (e.g., "claude-sonnet-4-20250514")

        Returns:
            True if both provider and model exist and are available
            False if either provider or model doesn't exist

        Raises:
            ValueError: If provider or model is an empty string

        Example:
            ```python
            from llm_pricing import LLMPricing

            pricing = LLMPricing()

            # Check if provider and model exist
            if pricing.validate(provider="anthropic", model="claude-3-opus-20250219"):
                result = pricing.calculate(
                    provider="anthropic",
                    model="claude-3-opus-20250219",
                    usage=TokenUsage(input_tokens=1000, output_tokens=500),
                )
                print(f"Cost: ${result.total_cost}")
            else:
                print("Provider or model not found")

            # Safe pattern for user input
            provider_id = "unknown-provider"
            model_id = "unknown-model"
            if not pricing.validate(provider=provider_id, model=model_id):
                print(f"Provider '{provider_id}' or model '{model_id}' not available")
            ```
        """
        if not provider or not model:
            raise ValueError("Provider and model names cannot be empty")

        providers = self.list_providers()
        if provider not in providers:
            return False

        provider_obj = providers[provider]
        if model not in provider_obj.models:
            return False

        model_obj = provider_obj.models[model]
        return model_obj.is_available

    # === Properties ===

    @property
    def provider_count(self) -> int:
        """Get the number of providers.

        Returns:
            Number of providers in the current database

        Example:
            ```python
            print(f"Available providers: {pricing.provider_count}")
            ```
        """
        return self._repo.provider_count

    @property
    def model_count(self) -> int:
        """Get the total number of models.

        Returns:
            Total number of models across all providers

        Example:
            ```python
            print(f"Available models: {pricing.model_count}")
            ```
        """
        return self._repo.model_count
