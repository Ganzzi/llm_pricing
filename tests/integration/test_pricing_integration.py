"""Integration tests for llm_pricing: pricing engine and rate limiter.

Covers:
- Token-to-cost calculation
- Quota enforcement (rate limiters)
- Multi-tenant billing isolation
- Pricing update propagation
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from llm_pricing import (
    LLMPricing,
    ModelInfo,
    ModelPrice,
    ModelRateLimits,
    Provider,
    ProviderTier,
    TokenUsage,
)
from llm_pricing.engine import PricingEngine
from llm_pricing.repository import create_repository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_provider(provider_id: str, tiers: list[str] | None = None) -> Provider:
    tier_ids = tiers or ["default", "pro"]
    return Provider(
        provider_id=provider_id,
        name=f"{provider_id} Provider",
        tiers={t: ProviderTier(tier_id=t, name=t.capitalize()) for t in tier_ids},
        models={},
    )


def make_model(
    model_id: str,
    provider_id: str,
    input_mtok: Decimal = Decimal("3.00"),
    output_mtok: Decimal = Decimal("15.00"),
    cache_read_mtok: Decimal | None = None,
    cache_write_mtok: Decimal | None = None,
    rate_limiters: dict | None = None,
) -> ModelInfo:
    return ModelInfo(
        model_id=model_id,
        name=f"{model_id} Model",
        provider_id=provider_id,
        pricing=ModelPrice(
            input_mtok=input_mtok,
            output_mtok=output_mtok,
            cache_read_mtok=cache_read_mtok,
            cache_write_mtok=cache_write_mtok,
        ),
        rate_limiters=rate_limiters or {},
    )


@pytest.fixture
def tmp_pricing():
    """Fresh LLMPricing instance per test (no shared state)."""
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        yield LLMPricing(local_path=tmp_path, package_root=tmp_path)


@pytest.fixture
def tmp_pricing_with_anthropic(tmp_pricing):
    """LLMPricing pre-loaded with a synthetic Anthropic-style provider."""
    p = tmp_pricing
    provider = make_provider("anthropic", tiers=["default", "free", "pro"])
    p.add_provider(provider)

    sonnet = make_model(
        model_id="claude-sonnet-4",
        provider_id="anthropic",
        input_mtok=Decimal("3.00"),
        output_mtok=Decimal("15.00"),
        cache_read_mtok=Decimal("0.30"),
        cache_write_mtok=Decimal("3.75"),
        rate_limiters={
            "free": ModelRateLimits(rpm=10, tpm=1_000_000),
            "pro": ModelRateLimits(rpm=50, tpm=5_000_000),
        },
    )
    p.add_model("anthropic", sonnet)
    return p


# ---------------------------------------------------------------------------
# 1. Token-to-cost calculation
# ---------------------------------------------------------------------------


class TestTokenToCostCalculation:
    """Verify that token counts produce the correct dollar amounts."""

    def test_basic_cost_calculation(self, tmp_pricing_with_anthropic):
        pricing = tmp_pricing_with_anthropic
        # 1 000 000 input tokens @ $3/1M = $3.00
        # 500 000 output tokens @ $15/1M = $7.50  → total $10.50
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=500_000)
        result = pricing.calculate(provider="anthropic", model="claude-sonnet-4", usage=usage)

        assert result.input_cost == Decimal("3.00")
        assert result.output_cost == Decimal("7.50")
        assert result.total_cost == Decimal("10.50")

    def test_zero_tokens_produce_zero_cost(self, tmp_pricing_with_anthropic):
        usage = TokenUsage(input_tokens=0, output_tokens=0)
        result = tmp_pricing_with_anthropic.calculate(
            provider="anthropic", model="claude-sonnet-4", usage=usage
        )
        assert result.total_cost == Decimal("0")

    def test_cache_read_cost(self, tmp_pricing_with_anthropic):
        # 1 000 000 cache-read tokens @ $0.30/1M = $0.30
        usage = TokenUsage(input_tokens=0, output_tokens=0, cache_read_tokens=1_000_000)
        result = tmp_pricing_with_anthropic.calculate(
            provider="anthropic", model="claude-sonnet-4", usage=usage
        )
        assert result.cache_read_cost == Decimal("0.30")

    def test_cache_write_cost(self, tmp_pricing_with_anthropic):
        # 1 000 000 cache-write tokens @ $3.75/1M = $3.75
        usage = TokenUsage(
            input_tokens=0, output_tokens=0, cache_creation_tokens=1_000_000
        )
        result = tmp_pricing_with_anthropic.calculate(
            provider="anthropic", model="claude-sonnet-4", usage=usage
        )
        assert result.cache_creation_cost == Decimal("3.75")

    def test_full_usage_breakdown(self, tmp_pricing_with_anthropic):
        usage = TokenUsage(
            input_tokens=500_000,
            output_tokens=200_000,
            cache_read_tokens=100_000,
            cache_creation_tokens=50_000,
        )
        result = tmp_pricing_with_anthropic.calculate(
            provider="anthropic", model="claude-sonnet-4", usage=usage
        )
        expected_input = (Decimal(500_000) / Decimal("1000000")) * Decimal("3.00")
        expected_output = (Decimal(200_000) / Decimal("1000000")) * Decimal("15.00")
        expected_cache_read = (Decimal(100_000) / Decimal("1000000")) * Decimal("0.30")
        expected_cache_write = (Decimal(50_000) / Decimal("1000000")) * Decimal("3.75")
        assert result.input_cost == expected_input
        assert result.output_cost == expected_output
        assert result.cache_read_cost == expected_cache_read
        assert result.cache_creation_cost == expected_cache_write

    def test_unknown_provider_raises(self, tmp_pricing_with_anthropic):
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        with pytest.raises(ValueError, match="not found"):
            tmp_pricing_with_anthropic.calculate(
                provider="nonexistent", model="some-model", usage=usage
            )

    def test_unknown_model_raises(self, tmp_pricing_with_anthropic):
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        with pytest.raises(ValueError, match="not found"):
            tmp_pricing_with_anthropic.calculate(
                provider="anthropic", model="nonexistent-model", usage=usage
            )

    def test_cost_proportional_to_token_count(self, tmp_pricing_with_anthropic):
        """Doubling tokens doubles cost."""
        small = TokenUsage(input_tokens=100_000, output_tokens=0)
        large = TokenUsage(input_tokens=200_000, output_tokens=0)
        r_small = tmp_pricing_with_anthropic.calculate(
            provider="anthropic", model="claude-sonnet-4", usage=small
        )
        r_large = tmp_pricing_with_anthropic.calculate(
            provider="anthropic", model="claude-sonnet-4", usage=large
        )
        assert r_large.input_cost == r_small.input_cost * 2


# ---------------------------------------------------------------------------
# 2. Quota enforcement / rate limiters
# ---------------------------------------------------------------------------


class TestRateLimiterEnforcement:
    """Verify that rate limit metadata is stored and accessible per tier."""

    def test_rate_limits_stored_on_model(self, tmp_pricing_with_anthropic):
        model = tmp_pricing_with_anthropic.list_models(provider="anthropic")[0]
        assert "free" in model.rate_limiters
        assert "pro" in model.rate_limiters

    def test_free_tier_rate_limits(self, tmp_pricing_with_anthropic):
        model = tmp_pricing_with_anthropic.list_models(provider="anthropic")[0]
        free_limits = model.rate_limiters["free"]
        assert free_limits.rpm == 10
        assert free_limits.tpm == 1_000_000

    def test_pro_tier_rate_limits_higher_than_free(self, tmp_pricing_with_anthropic):
        model = tmp_pricing_with_anthropic.list_models(provider="anthropic")[0]
        assert model.rate_limiters["pro"].rpm > model.rate_limiters["free"].rpm
        assert model.rate_limiters["pro"].tpm > model.rate_limiters["free"].tpm

    def test_model_without_rate_limits(self, tmp_pricing):
        provider = make_provider("no-limits-ai")
        tmp_pricing.add_provider(provider)
        model = make_model("basic-v1", "no-limits-ai")  # no rate_limiters kwarg
        tmp_pricing.add_model("no-limits-ai", model)

        stored = tmp_pricing.list_models(provider="no-limits-ai")[0]
        assert stored.rate_limiters == {}

    def test_rate_limits_persist_after_reload(self, tmp_pricing_with_anthropic):
        """Rate limiters survive a snapshot/reload cycle."""
        info = tmp_pricing_with_anthropic.store_snapshot()
        assert info is not None

        model = tmp_pricing_with_anthropic.list_models(provider="anthropic")[0]
        assert model.rate_limiters["pro"].tpm == 5_000_000

    def test_rpd_rate_limit(self, tmp_pricing):
        provider = make_provider("myai")
        tmp_pricing.add_provider(provider)
        model = make_model(
            "myai-v1",
            "myai",
            rate_limiters={"default": ModelRateLimits(rpd=500)},
        )
        tmp_pricing.add_model("myai", model)
        stored = tmp_pricing.list_models(provider="myai")[0]
        assert stored.rate_limiters["default"].rpd == 500


# ---------------------------------------------------------------------------
# 3. Multi-tenant billing isolation
# ---------------------------------------------------------------------------


class TestMultiTenantBillingIsolation:
    """Verify that separate LLMPricing instances (tenants) don't share state."""

    def test_separate_instances_have_isolated_providers(self):
        with TemporaryDirectory() as d1, TemporaryDirectory() as d2:
            p1 = LLMPricing(local_path=Path(d1))
            p2 = LLMPricing(local_path=Path(d2))

            p1.add_provider(make_provider("tenant-a-ai"))
            # p2 should NOT see tenant-a-ai
            assert "tenant-a-ai" not in p2.list_providers()

    def test_separate_instances_have_isolated_models(self):
        with TemporaryDirectory() as d1, TemporaryDirectory() as d2:
            p1 = LLMPricing(local_path=Path(d1))
            p2 = LLMPricing(local_path=Path(d2))

            provider_a = make_provider("shared-provider")
            provider_b = make_provider("shared-provider")

            p1.add_provider(provider_a)
            p2.add_provider(provider_b)

            model_a = make_model("model-a", "shared-provider", input_mtok=Decimal("1.00"))
            model_b = make_model("model-b", "shared-provider", input_mtok=Decimal("9.99"))

            p1.add_model("shared-provider", model_a)
            p2.add_model("shared-provider", model_b)

            assert len(p1.list_models(provider="shared-provider")) == 1
            assert p1.list_models(provider="shared-provider")[0].model_id == "model-a"

            assert len(p2.list_models(provider="shared-provider")) == 1
            assert p2.list_models(provider="shared-provider")[0].model_id == "model-b"

    def test_cost_calculation_uses_own_pricing(self):
        """Two tenants with same model but different prices compute different costs."""
        with TemporaryDirectory() as d1, TemporaryDirectory() as d2:
            p1 = LLMPricing(local_path=Path(d1))
            p2 = LLMPricing(local_path=Path(d2))

            for p, input_price in [(p1, Decimal("1.00")), (p2, Decimal("5.00"))]:
                p.add_provider(make_provider("shared-ai"))
                p.add_model(
                    "shared-ai",
                    make_model(
                        "shared-model", "shared-ai", input_mtok=input_price, output_mtok=Decimal("2.00")
                    ),
                )

            usage = TokenUsage(input_tokens=1_000_000, output_tokens=0)
            r1 = p1.calculate(provider="shared-ai", model="shared-model", usage=usage)
            r2 = p2.calculate(provider="shared-ai", model="shared-model", usage=usage)

            assert r1.input_cost == Decimal("1.00")
            assert r2.input_cost == Decimal("5.00")

    def test_deleting_model_in_one_tenant_does_not_affect_other(self):
        with TemporaryDirectory() as d1, TemporaryDirectory() as d2:
            p1 = LLMPricing(local_path=Path(d1))
            p2 = LLMPricing(local_path=Path(d2))

            for p in (p1, p2):
                p.add_provider(make_provider("acme"))
                p.add_model("acme", make_model("acme-v1", "acme"))

            p1.delete_model("acme", "acme-v1")
            assert len(p1.list_models(provider="acme")) == 0
            assert len(p2.list_models(provider="acme")) == 1


# ---------------------------------------------------------------------------
# 4. Pricing update propagation
# ---------------------------------------------------------------------------


class TestPricingUpdatePropagation:
    """Verify that adding/updating models and providers is immediately visible."""

    def test_new_model_is_immediately_queryable(self, tmp_pricing):
        tmp_pricing.add_provider(make_provider("newco"))
        tmp_pricing.add_model("newco", make_model("newco-v1", "newco"))

        assert tmp_pricing.validate(provider="newco", model="newco-v1")

    def test_new_model_immediately_usable_for_cost_calculation(self, tmp_pricing):
        tmp_pricing.add_provider(make_provider("fastai"))
        tmp_pricing.add_model(
            "fastai", make_model("fast-v1", "fastai", input_mtok=Decimal("2.00"))
        )
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=0)
        result = tmp_pricing.calculate(provider="fastai", model="fast-v1", usage=usage)
        assert result.input_cost == Decimal("2.00")

    def test_deleted_model_no_longer_queryable(self, tmp_pricing):
        tmp_pricing.add_provider(make_provider("tempco"))
        tmp_pricing.add_model("tempco", make_model("temp-v1", "tempco"))
        assert tmp_pricing.validate(provider="tempco", model="temp-v1")

        tmp_pricing.delete_model("tempco", "temp-v1")
        assert not tmp_pricing.validate(provider="tempco", model="temp-v1")

    def test_deleted_provider_removes_all_models(self, tmp_pricing):
        tmp_pricing.add_provider(make_provider("goner"))
        tmp_pricing.add_model("goner", make_model("goner-v1", "goner"))
        tmp_pricing.add_model("goner", make_model("goner-v2", "goner"))

        tmp_pricing.delete_provider("goner")
        assert "goner" not in tmp_pricing.list_providers()
        assert tmp_pricing.validate(provider="goner", model="goner-v1") is False
        assert tmp_pricing.validate(provider="goner", model="goner-v2") is False

    def test_snapshot_captures_current_state(self, tmp_pricing):
        tmp_pricing.add_provider(make_provider("snap-only-provider"))
        tmp_pricing.add_model(
            "snap-only-provider", make_model("snap-model", "snap-only-provider")
        )
        info = tmp_pricing.store_snapshot()
        assert info.provider_count >= 1
        assert info.model_count >= 1

    def test_provider_count_reflects_additions_and_deletions(self, tmp_pricing):
        initial = tmp_pricing.provider_count
        tmp_pricing.add_provider(make_provider("new-one"))
        assert tmp_pricing.provider_count == initial + 1

        tmp_pricing.delete_provider("new-one")
        assert tmp_pricing.provider_count == initial

    def test_model_count_reflects_additions_and_deletions(self, tmp_pricing):
        tmp_pricing.add_provider(make_provider("counttest"))
        initial = tmp_pricing.model_count

        tmp_pricing.add_model("counttest", make_model("m1", "counttest"))
        tmp_pricing.add_model("counttest", make_model("m2", "counttest"))
        assert tmp_pricing.model_count == initial + 2

        tmp_pricing.delete_model("counttest", "m1")
        assert tmp_pricing.model_count == initial + 1

    def test_pricing_engine_uses_updated_price_immediately(self, tmp_pricing):
        """Delete old model and add replacement with new price — engine reflects it."""
        tmp_pricing.add_provider(make_provider("dynamic"))
        tmp_pricing.add_model(
            "dynamic", make_model("dm", "dynamic", input_mtok=Decimal("1.00"))
        )
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=0)
        r1 = tmp_pricing.calculate(provider="dynamic", model="dm", usage=usage)
        assert r1.input_cost == Decimal("1.00")

        # Replace model with updated pricing
        tmp_pricing.delete_model("dynamic", "dm")
        tmp_pricing.add_model(
            "dynamic", make_model("dm", "dynamic", input_mtok=Decimal("4.00"))
        )
        r2 = tmp_pricing.calculate(provider="dynamic", model="dm", usage=usage)
        assert r2.input_cost == Decimal("4.00")
