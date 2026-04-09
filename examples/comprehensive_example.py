#!/usr/bin/env python3
"""
Comprehensive example demonstrating LLM Pricing features.

This example shows how to:
1. Calculate pricing for various LLM models
2. List available providers and models
3. Add custom providers and models
4. Store snapshots of pricing data
"""

from decimal import Decimal
from llm_pricing import (
    LLMPricing,
    TokenUsage,
    Provider,
    ProviderTier,
    ModelInfo,
    ModelPrice,
    ModelRateLimits,
    TieredPrice,
    PriceTier,
    calculate_cost,
)


def example_1_basic_calculation():
    """Example 1: Basic cost calculation."""
    print("\n" + "=" * 70)
    print("Example 1: Basic Cost Calculation")
    print("=" * 70)

    pricing = LLMPricing()

    # Add a provider first (if not already loaded from snapshot)
    providers = pricing.list_providers()
    if "openai" not in providers:
        openai_provider = Provider(
            provider_id="openai",
            name="OpenAI",
            tiers={
                "default": ProviderTier(
                    tier_id="default",
                    name="Default",
                ),
            },
            models={},
        )
        pricing.add_provider(openai_provider)

    # Create and add a model (if not already exists)
    openai_models = pricing.list_models("openai")
    if not any(m.model_id == "gpt-4o-mini" for m in openai_models):
        openai_model = ModelInfo(
            model_id="gpt-4o-mini",
            name="GPT-4o Mini",
            provider_id="openai",
            pricing={
                "default": ModelPrice(
                    input_mtok=Decimal("0.15"),
                    output_mtok=Decimal("0.60"),
                ),
            },
        )
        pricing.add_model("openai", openai_model)

    # Calculate cost for GPT-4o Mini
    usage = TokenUsage(input_tokens=100000, output_tokens=50000)
    result = pricing.calculate(
        provider="openai",
        model="gpt-4o-mini",
        usage=usage,
    )

    print(f"\nModel: GPT-4o Mini")
    print(f"Input tokens: {usage.input_tokens:,}")
    print(f"Output tokens: {usage.output_tokens:,}")
    print(f"\nCost Breakdown:")
    print(f"  Input cost:  ${result.input_cost:.6f}")
    print(f"  Output cost: ${result.output_cost:.6f}")
    print(f"  Total cost:  ${result.total_cost:.6f}")


def example_2_list_providers():
    """Example 2: List all providers."""
    print("\n" + "=" * 70)
    print("Example 2: List All Providers")
    print("=" * 70)

    pricing = LLMPricing()
    providers = pricing.list_providers()

    print(f"\nTotal providers: {len(providers)}")
    for provider_id, provider in list(providers.items())[:3]:  # Show first 3
        print(f"\n  Provider: {provider.name} ({provider_id})")
        print(f"    Tiers: {len(provider.tiers)}")
        for tier_id, tier in provider.tiers.items():
            print(f"      - {tier.name} ({tier_id})")
        print(f"    Models: {len(provider.models)}")


def example_3_list_models():
    """Example 3: List models by provider."""
    print("\n" + "=" * 70)
    print("Example 3: List Models")
    print("=" * 70)

    pricing = LLMPricing()

    # Add Anthropic provider if not already there
    try:
        pricing.list_models(provider="anthropic")
    except:
        # Provider doesn't exist, add it
        anthropic_provider = Provider(
            provider_id="anthropic",
            name="Anthropic",
            tiers={
                "default": ProviderTier(
                    tier_id="default",
                    name="Default",
                ),
            },
            models={},
        )
        pricing.add_provider(anthropic_provider)

        # Add a few Anthropic models
        for model_id in ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]:
            model = ModelInfo(
                model_id=model_id,
                name=model_id.replace("-", " ").title(),
                provider_id="anthropic",
                pricing={
                    "default": ModelPrice(
                        input_mtok=Decimal("3.0"),
                        output_mtok=Decimal("15.0"),
                    ),
                },
            )
            pricing.add_model("anthropic", model)

    # All models
    all_models = pricing.list_models()
    print(f"\nTotal models across all providers: {len(all_models)}")

    # Anthropic models only
    anthropic_models = pricing.list_models(provider="anthropic")
    print(f"\nAnthropic models: {len(anthropic_models)}")
    for i, model in enumerate(anthropic_models[:5], 1):  # Show first 5
        print(f"  {i}. {model.name} ({model.model_id})")


def example_4_add_custom_provider():
    """Example 4: Add a custom provider."""
    print("\n" + "=" * 70)
    print("Example 4: Add Custom Provider")
    print("=" * 70)

    pricing = LLMPricing()
    initial_count = pricing.provider_count
    print(f"\nInitial provider count: {initial_count}")

    # Create a custom provider
    custom_provider = Provider(
        provider_id="my-company",
        name="My Company AI",
        tiers={
            "free": ProviderTier(tier_id="free", name="Free"),
            "pro": ProviderTier(tier_id="pro", name="Professional"),
        },
        models={},
    )

    # Add the provider
    pricing.add_provider(custom_provider)
    print(f"Added custom provider: {custom_provider.name}")
    print(f"New provider count: {pricing.provider_count}")


def example_5_add_custom_model():
    """Example 5: Add a custom model to a provider."""
    print("\n" + "=" * 70)
    print("Example 5: Add Custom Model")
    print("=" * 70)

    pricing = LLMPricing()

    # Create custom provider first (skip if already exists)
    providers = pricing.list_providers()
    if "my-company" not in providers:
        custom_provider = Provider(
            provider_id="my-company",
            name="My Company AI",
            tiers={
                "free": ProviderTier(tier_id="free", name="Free"),
                "pro": ProviderTier(tier_id="pro", name="Professional"),
            },
            models={},
        )
        pricing.add_provider(custom_provider)

    initial_model_count = pricing.model_count
    print(f"\nInitial model count: {initial_model_count}")

    # Create a custom model
    custom_model = ModelInfo(
        model_id="my-llm-v1",
        name="My LLM Version 1",
        provider_id="my-company",
        pricing={
            "default": ModelPrice(
                input_mtok=Decimal("0.50"),
                output_mtok=Decimal("1.00"),
            ),
            "pro": ModelPrice(
                input_mtok=Decimal("0.40"),
                output_mtok=Decimal("0.80"),
            ),
        },
        rate_limiters={
            "free": ModelRateLimits(rpm=10, tpm=100_000),
            "pro": ModelRateLimits(rpm=100, tpm=1_000_000),
        },
    )

    # Add the model
    pricing.add_model("my-company", custom_model)
    print(f"\nAdded custom model: {custom_model.name}")
    print(f"Model ID: {custom_model.model_id}")
    print(f"Tiers: {list(custom_model.pricing.keys())}")
    print(f"New model count: {pricing.model_count}")

    # Calculate cost for the custom model
    usage = TokenUsage(input_tokens=10000, output_tokens=5000)
    result = pricing.calculate(
        provider="my-company",
        model="my-llm-v1",
        usage=usage,
        tier="pro",
    )
    print(f"\nCost for 10K input + 5K output tokens (pro tier):")
    print(f"  Input cost:  ${result.input_cost:.6f}")
    print(f"  Output cost: ${result.output_cost:.6f}")
    print(f"  Total cost:  ${result.total_cost:.6f}")


def example_6_tiered_pricing():
    """Example 6: Model with tiered pricing (like Claude Sonnet 4.5)."""
    print("\n" + "=" * 70)
    print("Example 6: Tiered Pricing")
    print("=" * 70)

    pricing = LLMPricing()

    # Create provider with tiered pricing
    providers = pricing.list_providers()
    if "tiered-provider" not in providers:
        tiered_provider = Provider(
            provider_id="tiered-provider",
            name="Tiered Provider",
            tiers={
                "default": ProviderTier(tier_id="default", name="Default"),
            },
            models={},
        )
        pricing.add_provider(tiered_provider)

    # Create model with tiered pricing
    tiered_model = ModelInfo(
        model_id="tiered-model",
        name="Model with Tiered Pricing",
        provider_id="tiered-provider",
        pricing={
            "default": ModelPrice(
                input_mtok=TieredPrice(
                    base=Decimal("3.00"),  # $3 per 1M tokens for first 200K
                    tiers=[
                        PriceTier(
                            start=200000,  # After 200K tokens
                            price=Decimal("6.00"),  # $6 per 1M tokens
                        ),
                    ],
                ),
                output_mtok=Decimal("2.00"),
            ),
        },
    )

    pricing.add_model("tiered-provider", tiered_model)
    print(f"\nAdded model with tiered input pricing:")
    print(f"  Base rate: $3.00 per 1M tokens")
    print(f"  Tier rate: $6.00 per 1M tokens after 200K tokens")

    # Calculate for different token amounts
    for input_tokens in [100000, 200000, 300000]:
        usage = TokenUsage(input_tokens=input_tokens, output_tokens=0)
        result = pricing.calculate(
            provider="tiered-provider",
            model="tiered-model",
            usage=usage,
        )
        print(f"\n  {input_tokens:,} input tokens -> ${result.input_cost:.6f}")


def example_7_convenience_function():
    """Example 7: Use convenience function."""
    print("\n" + "=" * 70)
    print("Example 7: Convenience Function")
    print("=" * 70)

    # First ensure a model exists
    pricing = LLMPricing()
    if not pricing.list_models("openai"):
        openai_model = ModelInfo(
            model_id="gpt-4o-mini",
            name="GPT-4o Mini",
            provider_id="openai",
            pricing={
                "default": ModelPrice(
                    input_mtok=Decimal("0.15"),
                    output_mtok=Decimal("0.60"),
                ),
            },
        )
        pricing.add_model("openai", openai_model)

    # Method 1: Using TokenUsage object
    usage = TokenUsage(input_tokens=50000, output_tokens=25000)
    result = calculate_cost(
        provider="openai",
        model="gpt-4o-mini",
        usage=usage,
    )

    print(f"\nMethod 1: Using TokenUsage object")
    print(f"  Cost: ${result.total_cost:.6f}")

    # Method 2: Using direct token counts
    result = calculate_cost(
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=50000,
        output_tokens=25000,
    )

    print(f"\nMethod 2: Using direct token counts")
    print(f"  Cost: ${result.total_cost:.6f}")


def example_8_store_snapshot():
    """Example 8: Store a snapshot of pricing data."""
    print("\n" + "=" * 70)
    print("Example 8: Store Snapshot")
    print("=" * 70)

    pricing = LLMPricing()

    # Add some custom data
    if "snapshot-provider" not in pricing.list_providers():
        custom_provider = Provider(
            provider_id="snapshot-provider",
            name="Snapshot Provider",
            tiers={
                "default": ProviderTier(tier_id="default", name="Default"),
            },
            models={},
        )
        pricing.add_provider(custom_provider)

        custom_model = ModelInfo(
            model_id="snapshot-model",
            name="Snapshot Model",
            provider_id="snapshot-provider",
            pricing={
                "default": ModelPrice(
                    input_mtok=Decimal("1.00"),
                    output_mtok=Decimal("2.00"),
                ),
            },
        )
        pricing.add_model("snapshot-provider", custom_model)

    # Store snapshot
    print(f"\nStoring snapshot...")
    snapshot_info = pricing.store_snapshot()

    print(f"\nSnapshot created successfully!")
    print(f"  Filename: {snapshot_info.filename}")
    print(f"  Path: {snapshot_info.path}")
    print(f"  Timestamp: {snapshot_info.timestamp}")
    print(f"  Providers: {snapshot_info.provider_count}")
    print(f"  Models: {snapshot_info.model_count}")


def example_9_cleanup_data():
    """Example 9: Clean up data - delete models and providers."""
    print("\n" + "=" * 70)
    print("Example 9: Cleanup Data")
    print("=" * 70)

    pricing = LLMPricing()

    initial_providers = pricing.provider_count
    initial_models = pricing.model_count
    print(f"\nInitial state:")
    print(f"  Providers: {initial_providers}")
    print(f"  Models: {initial_models}")

    # Delete specific models
    try:
        pricing.delete_model("openai", "gpt-4o-mini")
        print(f"\nDeleted model: openai/gpt-4o-mini")
    except Exception as e:
        print(f"\nSkipping model delete (not found): {e}")

    # Delete providers
    for provider_id in ["snapshot-provider", "tiered-provider", "my-company"]:
        try:
            pricing.delete_provider(provider_id)
            print(f"Deleted provider: {provider_id}")
        except Exception as e:
            print(f"Provider not found: {provider_id}")

    # Show final state
    print(f"\nFinal state:")
    print(f"  Providers: {pricing.provider_count}")
    print(f"  Models: {pricing.model_count}")
    print(f"  Deleted {initial_providers - pricing.provider_count} providers")
    print(f"  Deleted {initial_models - pricing.model_count} models")

    # Store final snapshot after cleanup
    print(f"\nStoring final snapshot after cleanup...")
    snapshot_info = pricing.store_snapshot()
    print(f"Snapshot: {snapshot_info.filename}")
    print(f"  Providers: {snapshot_info.provider_count}")
    print(f"  Models: {snapshot_info.model_count}")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("LLM Pricing Package - Feature Demonstration")
    print("=" * 70)

    try:
        example_1_basic_calculation()
        example_2_list_providers()
        example_3_list_models()
        example_4_add_custom_provider()
        example_5_add_custom_model()
        example_6_tiered_pricing()
        example_7_convenience_function()
        example_8_store_snapshot()
        example_9_cleanup_data()

        print("\n" + "=" * 70)
        print("[SUCCESS] All examples completed successfully!")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
