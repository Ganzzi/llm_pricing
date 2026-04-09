"""Unit tests for the repository layer."""

import pytest
from pathlib import Path
from decimal import Decimal
from tempfile import TemporaryDirectory

pytestmark = pytest.mark.unit

from llm_pricing.repository import PricingRepository, create_repository
from llm_pricing.storage import LocalStorage, DataVersionManager, StorageConfig
from llm_pricing.models import (
    PricingDatabase,
    Provider,
    ProviderTier,
    ModelInfo,
    ModelPrice,
    TieredPrice,
    PriceTier,
    ModelRateLimits,
)
from llm_pricing.exceptions import ValidationError


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
def sample_provider():
    """Create a sample provider."""
    return Provider(
        provider_id="test-provider",
        name="Test Provider",
        description="A test provider",
        tiers={
            "free": ProviderTier(tier_id="free", name="Free", description="Free tier"),
            "pro": ProviderTier(tier_id="pro", name="Pro", description="Pro tier"),
        },
        models={},
    )


@pytest.fixture
def sample_model():
    """Create a sample model."""
    return ModelInfo(
        model_id="test-model-v1",
        name="Test Model v1",
        provider_id="test-provider",
        description="A test model",
        pricing=ModelPrice(
            input_mtok=Decimal("1.0"),
            output_mtok=Decimal("2.0"),
        ),
        rate_limiters={
            "free": ModelRateLimits(rpm=10, tpm=100000),
            "pro": ModelRateLimits(rpm=100, tpm=1000000),
        },
    )


class TestPricingRepositoryInitialization:
    """Tests for repository initialization."""

    def test_init_with_storage_backends(self, temp_storage):
        """Test repository initialization with storage backends."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        assert repo is not None
        assert repo.provider_count == 0
        assert repo.model_count == 0

    def test_lazy_loading(self, temp_storage):
        """Test that data is loaded lazily on first access."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        # No data loaded yet
        assert repo._data is None
        # Access triggers load
        providers = repo.list_providers()
        assert repo._data is not None
        assert providers == {}

    def test_init_from_empty_storage(self, temp_storage):
        """Test initialization when no data exists."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        assert repo.provider_count == 0
        assert repo.model_count == 0
        # Local file should now exist
        assert temp_storage["local_storage"].exists()


class TestListProviders:
    """Tests for list_providers method."""

    def test_list_empty_providers(self, temp_storage):
        """Test listing when no providers exist."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        providers = repo.list_providers()
        assert providers == {}

    def test_list_multiple_providers(self, temp_storage, sample_provider):
        """Test listing multiple providers."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )

        # Add providers
        provider1 = sample_provider
        provider2 = Provider(
            provider_id="another-provider",
            name="Another Provider",
            tiers={},
            models={},
        )
        repo.add_provider(provider1)
        repo.add_provider(provider2)

        providers = repo.list_providers()
        assert len(providers) == 2
        assert "test-provider" in providers
        assert "another-provider" in providers

    def test_list_providers_returns_copy(self, temp_storage, sample_provider):
        """Test that list_providers returns a copy, not reference."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        repo.add_provider(sample_provider)

        providers1 = repo.list_providers()
        providers2 = repo.list_providers()

        # Should be equal but different objects
        assert providers1 == providers2
        assert providers1 is not providers2


class TestListModels:
    """Tests for list_models method."""

    def test_list_all_models_empty(self, temp_storage):
        """Test listing models when none exist."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        models = repo.list_models()
        assert models == []

    def test_list_all_models(self, temp_storage, sample_provider, sample_model):
        """Test listing all models."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        repo.add_provider(sample_provider)
        repo.add_model("test-provider", sample_model)

        models = repo.list_models()
        assert len(models) == 1
        assert models[0].model_id == "test-model-v1"

    def test_list_models_by_provider(self, temp_storage, sample_provider, sample_model):
        """Test listing models filtered by provider."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        repo.add_provider(sample_provider)
        repo.add_model("test-provider", sample_model)

        models = repo.list_models(provider_id="test-provider")
        assert len(models) == 1
        assert models[0].model_id == "test-model-v1"

    def test_list_models_invalid_provider(self, temp_storage):
        """Test listing models with invalid provider ID."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        with pytest.raises(ValidationError, match="Provider 'nonexistent' not found"):
            repo.list_models(provider_id="nonexistent")

    def test_list_models_multiple_providers(self, temp_storage, sample_model):
        """Test listing models from multiple providers."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )

        # Create two providers
        provider1 = Provider(
            provider_id="provider-1",
            name="Provider 1",
            tiers={},
            models={},
        )
        provider2 = Provider(
            provider_id="provider-2",
            name="Provider 2",
            tiers={},
            models={},
        )

        repo.add_provider(provider1)
        repo.add_provider(provider2)

        # Add model to first provider
        model1 = sample_model
        repo.add_model("provider-1", model1)

        # Add different model to second provider
        model2 = ModelInfo(
            model_id="test-model-v2",
            name="Test Model v2",
            provider_id="provider-2",
            pricing=ModelPrice(
                input_mtok=Decimal("1.5"),
                output_mtok=Decimal("2.5"),
            ),
            rate_limiters={},
        )
        repo.add_model("provider-2", model2)

        # List all models
        all_models = repo.list_models()
        assert len(all_models) == 2

        # List models per provider
        p1_models = repo.list_models(provider_id="provider-1")
        assert len(p1_models) == 1
        assert p1_models[0].model_id == "test-model-v1"

        p2_models = repo.list_models(provider_id="provider-2")
        assert len(p2_models) == 1
        assert p2_models[0].model_id == "test-model-v2"


class TestGetModel:
    """Tests for get_model method."""

    def test_get_existing_model(self, temp_storage, sample_provider, sample_model):
        """Test getting an existing model."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        repo.add_provider(sample_provider)
        repo.add_model("test-provider", sample_model)

        model = repo.get_model("test-provider", "test-model-v1")
        assert model is not None
        assert model.model_id == "test-model-v1"

    def test_get_nonexistent_model(self, temp_storage, sample_provider):
        """Test getting a model that doesn't exist."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        repo.add_provider(sample_provider)

        model = repo.get_model("test-provider", "nonexistent")
        assert model is None

    def test_get_model_from_nonexistent_provider(self, temp_storage):
        """Test getting a model from a provider that doesn't exist."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )

        model = repo.get_model("nonexistent", "some-model")
        assert model is None


class TestAddProvider:
    """Tests for add_provider method."""

    def test_add_provider_success(self, temp_storage, sample_provider):
        """Test adding a provider successfully."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        repo.add_provider(sample_provider)

        assert repo.provider_count == 1
        providers = repo.list_providers()
        assert "test-provider" in providers

    def test_add_provider_persists(self, temp_storage, sample_provider):
        """Test that added provider is persisted to storage."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        repo.add_provider(sample_provider)

        # Create new repository instance from same storage
        repo2 = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        assert repo2.provider_count == 1
        assert "test-provider" in repo2.list_providers()

    def test_add_duplicate_provider(self, temp_storage, sample_provider):
        """Test adding a duplicate provider raises error."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        repo.add_provider(sample_provider)

        with pytest.raises(ValidationError, match="already exists"):
            repo.add_provider(sample_provider)

    def test_add_multiple_providers(self, temp_storage):
        """Test adding multiple distinct providers."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )

        provider1 = Provider(
            provider_id="provider-1",
            name="Provider 1",
            tiers={},
            models={},
        )
        provider2 = Provider(
            provider_id="provider-2",
            name="Provider 2",
            tiers={},
            models={},
        )

        repo.add_provider(provider1)
        repo.add_provider(provider2)

        assert repo.provider_count == 2


class TestAddModel:
    """Tests for add_model method."""

    def test_add_model_success(self, temp_storage, sample_provider, sample_model):
        """Test adding a model successfully."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        repo.add_provider(sample_provider)
        repo.add_model("test-provider", sample_model)

        assert repo.model_count == 1
        model = repo.get_model("test-provider", "test-model-v1")
        assert model is not None

    def test_add_model_persists(self, temp_storage, sample_provider, sample_model):
        """Test that added model is persisted to storage."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        repo.add_provider(sample_provider)
        repo.add_model("test-provider", sample_model)

        # Create new repository instance from same storage
        repo2 = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        assert repo2.model_count == 1
        model = repo2.get_model("test-provider", "test-model-v1")
        assert model is not None

    def test_add_model_to_nonexistent_provider(self, temp_storage, sample_model):
        """Test adding a model to a provider that doesn't exist."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        with pytest.raises(ValidationError, match="not found"):
            repo.add_model("nonexistent", sample_model)

    def test_add_duplicate_model(self, temp_storage, sample_provider, sample_model):
        """Test adding a duplicate model raises error."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        repo.add_provider(sample_provider)
        repo.add_model("test-provider", sample_model)

        with pytest.raises(ValidationError, match="already exists"):
            repo.add_model("test-provider", sample_model)

    def test_add_multiple_models_to_provider(self, temp_storage, sample_provider):
        """Test adding multiple models to a provider."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        repo.add_provider(sample_provider)

        model1 = ModelInfo(
            model_id="model-1",
            name="Model 1",
            provider_id="test-provider",
            pricing=ModelPrice(
                input_mtok=Decimal("1.0"),
                output_mtok=Decimal("2.0"),
            ),
            rate_limiters={},
        )
        model2 = ModelInfo(
            model_id="model-2",
            name="Model 2",
            provider_id="test-provider",
            pricing=ModelPrice(
                input_mtok=Decimal("1.5"),
                output_mtok=Decimal("2.5"),
            ),
            rate_limiters={},
        )

        repo.add_model("test-provider", model1)
        repo.add_model("test-provider", model2)

        assert repo.model_count == 2
        models = repo.list_models(provider_id="test-provider")
        assert len(models) == 2


class TestPropertyAccessors:
    """Tests for property accessors."""

    def test_provider_count(self, temp_storage):
        """Test provider_count property."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        assert repo.provider_count == 0

        provider = Provider(
            provider_id="p1",
            name="Provider 1",
            tiers={},
            models={},
        )
        repo.add_provider(provider)
        assert repo.provider_count == 1

    def test_model_count(self, temp_storage):
        """Test model_count property."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        assert repo.model_count == 0

        provider = Provider(
            provider_id="p1",
            name="Provider 1",
            tiers={},
            models={},
        )
        repo.add_provider(provider)

        model = ModelInfo(
            model_id="m1",
            name="Model 1",
            provider_id="p1",
            pricing=ModelPrice(
                input_mtok=Decimal("1.0"),
                output_mtok=Decimal("2.0"),
            ),
            rate_limiters={},
        )
        repo.add_model("p1", model)
        assert repo.model_count == 1


class TestCreateRepository:
    """Tests for create_repository factory function."""

    def test_create_repository_defaults(self):
        """Test creating repository with defaults."""
        with TemporaryDirectory() as tmpdir:
            temp_home = Path(tmpdir) / "home"
            temp_home.mkdir()

            # Can't easily mock home directory, so just test basic functionality
            repo = create_repository(local_path=temp_home / ".llm_pricing")
            assert repo is not None
            assert isinstance(repo, PricingRepository)

    def test_create_repository_custom_paths(self):
        """Test creating repository with custom paths."""
        with TemporaryDirectory() as tmpdir:
            local_dir = Path(tmpdir) / "custom_local"
            versions_dir = Path(tmpdir) / "custom_versions"

            repo = create_repository(
                local_path=local_dir,
                package_root=versions_dir,
            )
            assert repo is not None
            assert isinstance(repo, PricingRepository)

            # Local directory should be created
            assert local_dir.exists()

    def test_create_repository_creates_local_dir(self):
        """Test that create_repository creates local directory."""
        with TemporaryDirectory() as tmpdir:
            local_dir = Path(tmpdir) / "new_dir"

            assert not local_dir.exists()
            repo = create_repository(local_path=local_dir)
            assert local_dir.exists()


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_complete_workflow(self, temp_storage):
        """Test a complete workflow with provider and model."""
        repo = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )

        # Create provider
        provider = Provider(
            provider_id="anthropic",
            name="Anthropic",
            description="Claude models",
            tiers={
                "free": ProviderTier(
                    tier_id="free",
                    name="Free",
                    description="Free tier",
                ),
                "pro": ProviderTier(
                    tier_id="pro",
                    name="Pro",
                    description="Pro tier",
                ),
            },
            models={},
        )
        repo.add_provider(provider)

        # Create model with tiered pricing
        model = ModelInfo(
            model_id="claude-sonnet-4-5",
            name="Claude Sonnet 4.5",
            provider_id="anthropic",
            pricing=ModelPrice(
                input_mtok=TieredPrice(
                    base=Decimal("3.0"),
                    tiers=[
                        PriceTier(start=200000, price=Decimal("6.0")),
                    ],
                ),
                output_mtok=TieredPrice(
                    base=Decimal("15.0"),
                    tiers=[
                        PriceTier(start=50000, price=Decimal("30.0")),
                    ],
                ),
            ),
            rate_limiters={
                "free": ModelRateLimits(rpm=10, tpm=1000000),
                "pro": ModelRateLimits(rpm=50, tpm=5000000),
            },
        )
        repo.add_model("anthropic", model)

        # Verify
        assert repo.provider_count == 1
        assert repo.model_count == 1

        retrieved_model = repo.get_model("anthropic", "claude-sonnet-4-5")
        assert retrieved_model is not None
        assert retrieved_model.model_id == "claude-sonnet-4-5"

        # Verify persistence
        repo2 = PricingRepository(
            temp_storage["local_storage"],
            temp_storage["version_manager"],
        )
        assert repo2.provider_count == 1
        assert repo2.model_count == 1
