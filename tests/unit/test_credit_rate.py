"""Unit tests for ModelPrice.credit_rate_per_mtok (additive field)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.unit

from llm_pricing import ModelPrice


def test_default_none_when_field_absent():
    """Field defaults to None when not provided."""
    pricing = ModelPrice(
        input_mtok=Decimal("1.25"),
        output_mtok=Decimal("10.00"),
    )
    assert pricing.credit_rate_per_mtok is None


def test_backwards_compatible_with_serialized_data_json():
    """Existing serialized payloads (no credit_rate key) still validate."""
    serialized = {
        "input_mtok": 1.25,
        "output_mtok": 10,
        "cache_write_mtok": None,
        "cache_read_mtok": 0.125,
    }
    pricing = ModelPrice.model_validate(serialized)
    assert pricing.credit_rate_per_mtok is None
    assert pricing.input_mtok == Decimal("1.25")
    assert pricing.cache_read_mtok == Decimal("0.125")


def test_round_trip_serialization_with_field_set():
    """Field survives python- and json-mode round trips."""
    pricing = ModelPrice(
        input_mtok=Decimal("1.25"),
        output_mtok=Decimal("10.00"),
        credit_rate_per_mtok=Decimal("5.00"),
    )
    from_python = ModelPrice.model_validate(pricing.model_dump())
    assert from_python.credit_rate_per_mtok == Decimal("5.00")

    from_json = ModelPrice.model_validate_json(pricing.model_dump_json())
    assert from_json.credit_rate_per_mtok == Decimal("5.00")


def test_negative_value_raises_validation_error():
    """Negative credit rates are rejected; zero is allowed."""
    with pytest.raises(ValidationError, match="non-negative"):
        ModelPrice(
            input_mtok=Decimal("1.25"),
            output_mtok=Decimal("10.00"),
            credit_rate_per_mtok=Decimal("-0.01"),
        )

    zero = ModelPrice(
        input_mtok=Decimal("1.25"),
        output_mtok=Decimal("10.00"),
        credit_rate_per_mtok=Decimal("0"),
    )
    assert zero.credit_rate_per_mtok == Decimal("0")


def test_calculate_behavior_unchanged():
    """calculate_* results are identical with and without the field."""
    base_kwargs = {
        "input_mtok": Decimal("3.00"),
        "output_mtok": Decimal("15.00"),
        "cache_write_mtok": Decimal("3.75"),
        "cache_read_mtok": Decimal("0.30"),
    }
    without_field = ModelPrice(**base_kwargs)
    with_field = ModelPrice(**base_kwargs, credit_rate_per_mtok=Decimal("7.50"))

    usage = 1_000_000
    for pricing in (without_field, with_field):
        assert pricing.calculate_input_cost(usage) == Decimal("3.00")
        assert pricing.calculate_output_cost(usage) == Decimal("15.00")
        assert pricing.calculate_cache_write_cost(usage) == Decimal("3.75")
        assert pricing.calculate_cache_read_cost(usage) == Decimal("0.30")

    partial_usage = 100_000
    assert without_field.calculate_input_cost(partial_usage) == Decimal("0.30")
    assert with_field.calculate_input_cost(partial_usage) == Decimal("0.30")
