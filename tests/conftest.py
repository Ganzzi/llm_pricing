"""Pytest configuration for llm_pricing package tests."""

import pytest


@pytest.fixture
def anyio_backend():
    """Configure pytest-anyio to use asyncio."""
    return "asyncio"
