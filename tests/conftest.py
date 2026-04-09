"""Pytest configuration for llm_pricing package tests."""

import uuid
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from llm_pricing import (
    LLMPricing,
    ModelInfo,
    ModelPrice,
    Provider,
    ProviderTier,
)
from llm_pricing.storage import DataVersionManager, LocalStorage, StorageConfig


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
def temp_config(tmp_path: Path):
    """Create a config with temporary directories."""
    return StorageConfig(
        local_data_dir=tmp_path / "local",
        data_versions_dir=tmp_path / "data_versions",
    )


@pytest.fixture
def pricing_instance():
    """Create a LLMPricing instance with a temporary directory."""
    with TemporaryDirectory() as tmpdir:
        pricing = LLMPricing(local_path=Path(tmpdir))
        yield pricing
