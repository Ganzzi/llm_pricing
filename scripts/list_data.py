#!/usr/bin/env python3
"""
Script to list and display all LLM pricing data.
Shows providers, tiers, models, pricing, and rate limiters.
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Optional, Union

# Add the parent directory to sys.path to import llm_pricing
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_pricing.storage.local_storage import LocalStorage
from llm_pricing.storage.config import StorageConfig
from llm_pricing.models import TieredPrice, PriceValue


def format_price_value(price: Optional[PriceValue]) -> str:
    """Format a price value for display, handling both Decimal and TieredPrice."""
    if price is None:
        return "-"

    if isinstance(price, TieredPrice):
        # Format tiered pricing
        result = f"${price.base:.4f}"
        if price.tiers:
            tier_parts = []
            for tier in price.tiers:
                tier_parts.append(f"${tier.price:.4f} after {tier.start:,}")
            result += f" (then {', '.join(tier_parts)} tokens)"
        return result
    elif isinstance(price, Decimal):
        return f"${price:.4f}" if price != 0 else "Free"
    else:
        # Handle raw numeric types
        return f"${price:.4f}" if price != 0 else "Free"


def format_price(price: Optional[Decimal]) -> str:
    """Format a simple decimal price value for display."""
    if price is None:
        return "-"
    return f"${price:.4f}" if price != 0 else "Free"


def format_rate_limit(value: Optional[int], unit: str) -> str:
    """Format a rate limit value for display."""
    if value is None:
        return "—"
    if value >= 1_000_000:
        return f"{value // 1_000_000}M {unit}"
    elif value >= 1_000:
        return f"{value // 1_000}K {unit}"
    else:
        return f"{value} {unit}"


def print_separator(char: str = "=", length: int = 80):
    """Print a separator line."""
    print(char * length)


def print_section(title: str):
    """Print a section header."""
    print_separator()
    print(f"\n{title.upper()}\n")
    print_separator()


def list_all_data():
    """Load and display all pricing data."""
    # Initialize storage config and load the data
    config = StorageConfig()
    storage = LocalStorage(config)
    db = storage.load()

    print_section("LLM Pricing Database Overview")
    print(f"Version: {db.version}")
    print(f"Total Providers: {len(db.providers)}")
    print(f"Total Models: {sum(len(p.models) for p in db.providers.values())}")
    print(f"Total Tiers: {sum(len(p.tiers) for p in db.providers.values())}")

    # Iterate through each provider
    for provider_id, provider in db.providers.items():
        print_section(f"{provider.name} Provider")
        print(f"API Endpoint: {provider.api_endpoint_pattern}")
        print(f"Documentation: {provider.documentation_url}")
        print(f"Available: {'Yes' if provider.is_available else 'No'}\n")

        # Display tiers
        print("TIERS:")
        print_separator("-")
        for tier_id, tier in provider.tiers.items():
            print(f"\n  [{tier_id}] {tier.name}")
            if tier.description:
                print(f"       Description: {tier.description}")
            print(f"       Available: {'Yes' if tier.is_available else 'No'}")

        # Display models
        print("\n\nMODELS:")
        print_separator("-")
        for model_id, model in provider.models.items():
            print(f"\n  [{model_id}] {model.name}")
            print(f"       Context Window: {model.context_window:,} tokens")
            if model.description:
                print(f"       Description: {model.description}")

            # Display pricing (now directly ModelPrice, not a dict)
            print(f"       Pricing:")
            pricing = model.pricing
            print(f"         Input: {format_price_value(pricing.input_mtok)}/M tokens")
            print(f"         Output: {format_price_value(pricing.output_mtok)}/M tokens")
            if pricing.cache_write_mtok:
                print(
                    f"         Cache Write: {format_price_value(pricing.cache_write_mtok)}/M tokens"
                )
            if pricing.cache_read_mtok:
                print(
                    f"         Cache Read: {format_price_value(pricing.cache_read_mtok)}/M tokens"
                )

            # Display rate limiters for each tier
            print(f"       Rate Limiters:")
            for tier_id, limits in sorted(model.rate_limiters.items()):
                tier_name = provider.tiers[tier_id].name if tier_id in provider.tiers else tier_id
                print(f"         {tier_name}:")

                if limits.rpm:
                    print(f"           RPM: {format_rate_limit(limits.rpm, 'requests/min')}")
                if limits.tpm:
                    print(f"           TPM: {format_rate_limit(limits.tpm, 'tokens/min')}")
                if limits.tpd:
                    print(f"           TPD: {format_rate_limit(limits.tpd, 'tokens/day')}")
                if limits.itpm:
                    print(f"           Input TPM: {format_rate_limit(limits.itpm, 'tokens/min')}")
                if limits.otpm:
                    print(f"           Output TPM: {format_rate_limit(limits.otpm, 'tokens/min')}")

                if not any([limits.rpm, limits.tpm, limits.tpd, limits.itpm, limits.otpm]):
                    print(f"           (No rate limits specified)")

    print("\n")
    print_separator()
    print("END OF PRICING DATABASE LISTING")
    print_separator()


if __name__ == "__main__":
    try:
        list_all_data()
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
