"""Tests for LLMPricing main class."""

import pytest
import tempfile
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import uuid

from llm_pricing import (
    LLMPricing,
    calculate_cost,
    TokenUsage,
    CostBreakdown,
    Provider,
    ModelInfo,
    ModelPrice,
    ProviderTier,
)
from llm_pricing.exceptions import ValidationError


def unique_id(prefix: str) -> str:
    """Generate unique ID using UUID."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def create_test_model(model_id: str, provider_id: str) -> ModelInfo:
    """Helper to create test ModelInfo."""
    return ModelInfo(
        model_id=model_id,
        name=f"{model_id} Model",
        provider_id=provider_id,
        pricing=ModelPrice(
            input_mtok=Decimal("1.00"),
            output_mtok=Decimal("2.00"),
            cache_read_mtok=None,
            cache_write_mtok=None,
        ),
    )


def create_test_provider(provider_id: str) -> Provider:
    """Helper to create test Provider."""
    return Provider(
        provider_id=provider_id,
        name=f"{provider_id} Provider",
        models={},
    )


class TestLLMPricingInitialization:
    """Tests for LLMPricing initialization."""

    def test_initialize_with_defaults(self):
        """Test initialization with default paths."""
        pricing = LLMPricing()
        assert pricing is not None
        assert pricing.provider_count >= 0
        assert pricing.model_count >= 0

    def test_initialize_with_custom_local_path(self):
        """Test initialization with custom local path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pricing = LLMPricing(local_path=Path(tmpdir))
            assert pricing is not None

    def test_properties_are_accessible(self):
        """Test that provider_count and model_count are accessible."""
        pricing = LLMPricing()
        count1 = pricing.provider_count
        count2 = pricing.model_count
        assert isinstance(count1, int)
        assert isinstance(count2, int)
        assert count1 >= 0
        assert count2 >= 0


class TestCalculateMethod:
    """Tests for the calculate() method."""

    @pytest.fixture
    def pricing(self):
        """Create a LLMPricing instance."""
        return LLMPricing()

    def test_calculate_basic(self, pricing):
        """Test basic cost calculation."""
        usage = TokenUsage(input_tokens=10000, output_tokens=5000)

        # Get available providers and models
        providers = pricing.list_providers()
        if not providers:
            pytest.skip("No providers available for testing")

        provider_id = next(iter(providers.keys()))
        models = pricing.list_models(provider=provider_id)

        if not models:
            pytest.skip(f"No models available for provider {provider_id}")

        model_id = models[0].model_id

        result = pricing.calculate(
            usage=usage,
            provider=provider_id,
            model=model_id,
        )

        assert isinstance(result, CostBreakdown)
        assert result.input_cost >= Decimal("0")
        assert result.output_cost >= Decimal("0")
        assert result.total_cost >= Decimal("0")

    def test_calculate_with_cache_tokens(self, pricing):
        """Test calculation with cache tokens."""
        usage = TokenUsage(
            input_tokens=5000,
            output_tokens=2000,
            cache_read_tokens=1000,
            cache_creation_tokens=500,
        )

        providers = pricing.list_providers()
        if not providers:
            pytest.skip("No providers available for testing")

        provider_id = next(iter(providers.keys()))
        models = pricing.list_models(provider=provider_id)

        if not models:
            pytest.skip(f"No models available for provider {provider_id}")

        model_id = models[0].model_id

        result = pricing.calculate(
            usage=usage,
            provider=provider_id,
            model=model_id,
        )

        assert isinstance(result, CostBreakdown)

    def test_calculate_invalid_provider(self, pricing):
        """Test calculation with invalid provider."""
        usage = TokenUsage(input_tokens=10000, output_tokens=5000)

        with pytest.raises(ValueError):
            pricing.calculate(
                usage=usage,
                provider="nonexistent-provider",
                model="some-model",
            )

    def test_calculate_invalid_model(self, pricing):
        """Test calculation with invalid model."""
        usage = TokenUsage(input_tokens=10000, output_tokens=5000)

        providers = pricing.list_providers()
        if not providers:
            pytest.skip("No providers available for testing")

        provider_id = next(iter(providers.keys()))

        with pytest.raises(ValueError):
            pricing.calculate(
                usage=usage,
                provider=provider_id,
                model="nonexistent-model",
            )

    def test_calculate_zero_tokens(self, pricing):
        """Test calculation with zero tokens."""
        usage = TokenUsage(input_tokens=0, output_tokens=0)

        providers = pricing.list_providers()
        if not providers:
            pytest.skip("No providers available for testing")

        provider_id = next(iter(providers.keys()))
        models = pricing.list_models(provider=provider_id)

        if not models:
            pytest.skip(f"No models available for provider {provider_id}")

        model_id = models[0].model_id

        result = pricing.calculate(
            usage=usage,
            provider=provider_id,
            model=model_id,
        )

        assert result.input_cost == Decimal("0")
        assert result.output_cost == Decimal("0")


class TestListProviders:
    """Tests for the list_providers() method."""

    def test_list_providers_returns_dict(self):
        """Test that list_providers returns a dictionary."""
        pricing = LLMPricing()
        providers = pricing.list_providers()

        assert isinstance(providers, dict)

    def test_list_providers_all_are_provider_objects(self):
        """Test that all returned items are Provider objects."""
        pricing = LLMPricing()
        providers = pricing.list_providers()

        for provider_id, provider in providers.items():
            assert isinstance(provider_id, str)
            assert isinstance(provider, Provider)

    def test_list_providers_contains_expected_structure(self):
        """Test that providers have expected attributes."""
        pricing = LLMPricing()
        providers = pricing.list_providers()

        for provider in providers.values():
            assert hasattr(provider, "provider_id")
            assert hasattr(provider, "name")
            assert hasattr(provider, "models")


class TestListModels:
    """Tests for the list_models() method."""

    def test_list_models_all(self):
        """Test listing all models."""
        pricing = LLMPricing()
        models = pricing.list_models()

        assert isinstance(models, list)
        for model in models:
            assert isinstance(model, ModelInfo)

    def test_list_models_filtered_by_provider(self):
        """Test listing models filtered by provider."""
        pricing = LLMPricing()
        providers = pricing.list_providers()

        if not providers:
            pytest.skip("No providers available for testing")

        provider_id = next(iter(providers.keys()))
        models = pricing.list_models(provider=provider_id)

        assert isinstance(models, list)

    def test_list_models_invalid_provider(self):
        """Test listing models with invalid provider."""
        pricing = LLMPricing()

        with pytest.raises(ValidationError):
            pricing.list_models(provider="nonexistent-provider")

    def test_list_models_contain_expected_attributes(self):
        """Test that models have expected attributes."""
        pricing = LLMPricing()
        models = pricing.list_models()

        if not models:
            pytest.skip("No models available for testing")

        model = models[0]
        assert hasattr(model, "model_id")
        assert hasattr(model, "pricing")


class TestAddProvider:
    """Tests for the add_provider() method."""

    def test_add_provider_success(self):
        """Test successfully adding a provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pricing = LLMPricing(local_path=Path(tmpdir))
            provider = create_test_provider("test-prov-1")

            pricing.add_provider(provider)

            # Verify it was added
            providers = pricing.list_providers()
            assert "test-prov-1" in providers
            assert providers["test-prov-1"].name == "test-prov-1 Provider"

    def test_add_provider_duplicate_raises_error(self):
        """Test that adding duplicate provider raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pricing = LLMPricing(local_path=Path(tmpdir))
            provider = create_test_provider("test-prov-dup")

            pricing.add_provider(provider)

            # Try to add again
            with pytest.raises(ValidationError):
                pricing.add_provider(provider)

    def test_add_provider_persists_to_storage(self):
        """Test that added provider persists across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # First instance - add provider
            pricing1 = LLMPricing(local_path=tmppath)
            provider = create_test_provider("test-prov-persist")
            pricing1.add_provider(provider)

            # Second instance - verify it exists
            pricing2 = LLMPricing(local_path=tmppath)
            providers = pricing2.list_providers()
            assert "test-prov-persist" in providers


class TestAddModel:
    """Tests for the add_model() method."""

    def test_add_model_success(self):
        """Test successfully adding a model."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pricing = LLMPricing(local_path=Path(tmpdir))

            # Add provider first
            provider = create_test_provider("test-prov-m1")
            pricing.add_provider(provider)

            # Add model
            model = create_test_model("test-model-1", "test-prov-m1")
            pricing.add_model("test-prov-m1", model)

            # Verify it was added
            models = pricing.list_models(provider="test-prov-m1")
            assert len(models) == 1
            assert models[0].model_id == "test-model-1"

    def test_add_model_nonexistent_provider(self):
        """Test adding model to nonexistent provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pricing = LLMPricing(local_path=Path(tmpdir))
            model = create_test_model("test-model-x", "nonexistent")

            with pytest.raises(ValidationError):
                pricing.add_model("nonexistent-provider", model)

    def test_add_model_duplicate_raises_error(self):
        """Test that adding duplicate model raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pricing = LLMPricing(local_path=Path(tmpdir))

            # Setup
            provider = create_test_provider("test-prov-m2")
            pricing.add_provider(provider)

            model = create_test_model("test-model-dup", "test-prov-m2")
            pricing.add_model("test-prov-m2", model)

            # Try to add again
            with pytest.raises(ValidationError):
                pricing.add_model("test-prov-m2", model)

    def test_add_model_persists_to_storage(self):
        """Test that added model persists across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # First instance
            pricing1 = LLMPricing(local_path=tmppath)
            provider = create_test_provider("test-prov-m3")
            pricing1.add_provider(provider)

            model = create_test_model("test-model-pers", "test-prov-m3")
            pricing1.add_model("test-prov-m3", model)

            # Second instance
            pricing2 = LLMPricing(local_path=tmppath)
            models = pricing2.list_models(provider="test-prov-m3")
            assert len(models) == 1
            assert models[0].model_id == "test-model-pers"


class TestStoreSnapshot:
    """Tests for the store_snapshot() method."""

    def test_store_snapshot_creates_file(self):
        """Test that store_snapshot creates a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            pricing = LLMPricing(local_path=tmppath)

            # Add some data with unique ID
            prov_id = unique_id("snap-prov")
            provider = create_test_provider(prov_id)
            pricing.add_provider(provider)

            # Store snapshot
            info = pricing.store_snapshot()

            assert info.path.exists()
            assert info.filename.endswith(".json")

    def test_store_snapshot_returns_snapshot_info(self):
        """Test that store_snapshot returns SnapshotInfo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pricing = LLMPricing(local_path=Path(tmpdir))

            info = pricing.store_snapshot()

            assert info is not None
            assert hasattr(info, "filename")
            assert hasattr(info, "path")
            assert hasattr(info, "timestamp")
            assert hasattr(info, "provider_count")
            assert hasattr(info, "model_count")

    def test_store_snapshot_includes_correct_data(self):
        """Test that snapshot contains the correct data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            pricing = LLMPricing(local_path=tmppath)

            # Add provider with unique ID
            prov_id = unique_id("test-snap-prov")
            provider = create_test_provider(prov_id)
            pricing.add_provider(provider)

            # Add model
            model = create_test_model("test-snap-model", prov_id)
            pricing.add_model(prov_id, model)

            # Store snapshot
            info = pricing.store_snapshot()

            assert info.provider_count >= 1
            assert info.model_count >= 1


class TestCalculateCostConvenienceFunction:
    """Tests for the calculate_cost() convenience function."""

    def test_calculate_cost_basic(self):
        """Test basic convenience function."""
        # Get some real data to test with
        pricing = LLMPricing()
        providers = pricing.list_providers()

        if not providers:
            pytest.skip("No providers available for testing")

        provider_id = next(iter(providers.keys()))
        models = pricing.list_models(provider=provider_id)

        if not models:
            pytest.skip(f"No models available for provider {provider_id}")

        model_id = models[0].model_id

        usage = TokenUsage(input_tokens=10000, output_tokens=5000)
        result = calculate_cost(
            usage=usage,
            provider=provider_id,
            model=model_id,
        )

        assert isinstance(result, CostBreakdown)
        assert result.total_cost >= Decimal("0")

    def test_calculate_cost_invalid_inputs(self):
        """Test convenience function with invalid inputs."""
        usage = TokenUsage(input_tokens=10000, output_tokens=5000)

        with pytest.raises(ValueError):
            calculate_cost(
                usage=usage,
                provider="nonexistent",
                model="nonexistent",
            )


class TestIntegration:
    """Integration tests combining multiple operations."""

    def test_full_workflow(self):
        """Test complete workflow: add provider, add model, calculate, snapshot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            pricing = LLMPricing(local_path=tmppath)

            # Add custom provider with unique ID
            prov_id = unique_id("custom")
            provider = create_test_provider(prov_id)
            pricing.add_provider(provider)

            # Add custom model
            model_id = unique_id("custom-model")
            model = create_test_model(model_id, prov_id)
            pricing.add_model(prov_id, model)

            # Calculate cost
            # Model created has: input_mtok=1.00, output_mtok=2.00
            usage = TokenUsage(input_tokens=1000000, output_tokens=500000)
            result = pricing.calculate(
                usage=usage,
                provider=prov_id,
                model=model_id,
            )

            # 1M tokens * 1.00 / 1M = 1.00
            assert result.input_cost == Decimal("1.00")
            # 500K tokens * 2.00 / 1M = 1.00
            assert result.output_cost == Decimal("1.00")
            assert result.total_cost == Decimal("2.00")

            # Store snapshot
            info = pricing.store_snapshot()
            assert info.path.exists()
            assert info.provider_count >= 1
            assert info.model_count >= 1
