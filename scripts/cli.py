#!/usr/bin/env python3
"""
Interactive CLI for LLM Pricing Database.

Usage:
    python scripts/cli.py
"""

import sys
from decimal import Decimal
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_pricing import LLMPricing, TokenUsage, Provider, ProviderTier, ModelInfo, ModelPrice
from llm_pricing.models import TieredPrice, PriceTier, ModelRateLimits


class CLIApp:
    """Interactive CLI application for LLM Pricing."""

    def __init__(self):
        """Initialize the CLI app."""
        self.pricing = LLMPricing()

    def clear_screen(self):
        """Clear the terminal screen."""
        import os

        os.system("cls" if os.name == "nt" else "clear")

    def print_header(self, title: str):
        """Print a formatted header."""
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80 + "\n")

    def print_menu(self):
        """Print the main menu."""
        self.print_header("LLM PRICING DATABASE - MAIN MENU")
        print("1. List all providers and models")
        print("2. View provider details")
        print("3. View model details")
        print("4. Calculate price from token usage")
        print("5. Add provider")
        print("6. Add model to provider")
        print("7. List available snapshots")
        print("8. Store snapshot")
        print("9. Database statistics")
        print("0. Exit")
        print()

    def list_providers_and_models(self):
        """List all providers and their models."""
        self.print_header("PROVIDERS AND MODELS")
        providers = self.pricing.list_providers()

        if not providers:
            print("No providers found in database.")
            return

        for provider_id, provider in sorted(providers.items()):
            print(f"\n[{provider_id}] {provider.name}")
            print(f"    Description: {provider.description or 'N/A'}")
            print(f"    API Endpoint: {provider.api_endpoint_pattern or 'N/A'}")
            print(f"    Models ({len(provider.models)}):")

            if not provider.models:
                print("        (No models)")
            else:
                for model_id, model in sorted(provider.models.items()):
                    print(f"      - {model_id}: {model.name}")

        input("\nPress Enter to continue...")

    def view_provider_details(self):
        """View detailed information about a provider."""
        self.print_header("VIEW PROVIDER DETAILS")
        providers = self.pricing.list_providers()

        if not providers:
            print("No providers found.")
            input("Press Enter to continue...")
            return

        print("Available providers:")
        provider_list = list(providers.items())
        for i, (provider_id, provider) in enumerate(provider_list, 1):
            print(f"{i}. {provider_id}: {provider.name}")

        try:
            choice = int(input("\nSelect provider (number): "))
            if 1 <= choice <= len(provider_list):
                provider_id, provider = provider_list[choice - 1]
                self._display_provider_details(provider_id, provider)
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input.")

        input("\nPress Enter to continue...")

    def _display_provider_details(self, provider_id: str, provider: Provider):
        """Display provider details."""
        print(f"\n{'=' * 80}")
        print(f"Provider: {provider.name}")
        print(f"ID: {provider_id}")
        print(f"Description: {provider.description or 'N/A'}")
        print(f"API Endpoint: {provider.api_endpoint_pattern or 'N/A'}")
        print(f"Documentation: {provider.documentation_url or 'N/A'}")
        print(f"Available: {'Yes' if provider.is_available else 'No'}")
        print(f"{'=' * 80}")

        print(f"\nTiers ({len(provider.tiers)}):")
        if provider.tiers:
            for tier_id, tier in sorted(provider.tiers.items()):
                status = "✓" if tier.is_available else "✗"
                print(f"  {status} [{tier_id}] {tier.name}")
                if tier.description:
                    print(f"      {tier.description}")
        else:
            print("  (No tiers)")

        print(f"\nModels ({len(provider.models)}):")
        if provider.models:
            for model_id, model in sorted(provider.models.items()):
                print(f"  • {model_id}")
                print(f"      Name: {model.name}")
                print(f"      Context Window: {model.context_window:,} tokens")
                if model.description:
                    print(f"      {model.description}")
        else:
            print("  (No models)")

    def view_model_details(self):
        """View detailed information about a model."""
        self.print_header("VIEW MODEL DETAILS")
        providers = self.pricing.list_providers()

        if not providers:
            print("No providers found.")
            input("Press Enter to continue...")
            return

        # Select provider
        print("Available providers:")
        provider_list = list(providers.items())
        for i, (provider_id, _) in enumerate(provider_list, 1):
            print(f"{i}. {provider_id}")

        try:
            p_choice = int(input("\nSelect provider (number): "))
            if not (1 <= p_choice <= len(provider_list)):
                print("Invalid selection.")
                input("Press Enter to continue...")
                return

            provider_id, provider = provider_list[p_choice - 1]

            if not provider.models:
                print("This provider has no models.")
                input("Press Enter to continue...")
                return

            # Select model
            print(f"\nModels in {provider_id}:")
            model_list = list(provider.models.items())
            for i, (model_id, _) in enumerate(model_list, 1):
                print(f"{i}. {model_id}")

            m_choice = int(input("\nSelect model (number): "))
            if 1 <= m_choice <= len(model_list):
                model_id, model = model_list[m_choice - 1]
                self._display_model_details(provider_id, model_id, model, provider)
            else:
                print("Invalid selection.")

        except ValueError:
            print("Invalid input.")

        input("\nPress Enter to continue...")

    def _display_model_details(
        self, provider_id: str, model_id: str, model: ModelInfo, provider: Provider
    ):
        """Display model details."""
        print(f"\n{'=' * 80}")
        print(f"Model: {model.name}")
        print(f"ID: {model_id}")
        print(f"Provider: {provider.name}")
        print(f"Context Window: {model.context_window:,} tokens")
        print(f"Description: {model.description or 'N/A'}")
        print(f"Available: {'Yes' if model.is_available else 'No'}")
        if model.prices_checked:
            print(f"Prices Last Checked: {model.prices_checked}")
        print(f"{'=' * 80}")

        # Pricing
        print(f"\nPricing:")
        pricing = model.pricing
        print(f"  Input: {self._format_price_value(pricing.input_mtok)}/M tokens")
        print(f"  Output: {self._format_price_value(pricing.output_mtok)}/M tokens")
        if pricing.cache_write_mtok:
            print(f"  Cache Write: {self._format_price_value(pricing.cache_write_mtok)}/M tokens")
        if pricing.cache_read_mtok:
            print(f"  Cache Read: {self._format_price_value(pricing.cache_read_mtok)}/M tokens")

        # Rate limiters
        print(f"\nRate Limiters:")
        if model.rate_limiters:
            for tier_id, limits in sorted(model.rate_limiters.items()):
                tier_name = provider.tiers[tier_id].name if tier_id in provider.tiers else tier_id
                print(f"  [{tier_name}]")
                if limits.rpm:
                    print(f"    RPM: {limits.rpm:,}")
                if limits.rpd:
                    print(f"    RPD: {limits.rpd:,}")
                if limits.tpm:
                    print(f"    TPM: {limits.tpm:,}")
                if limits.tpd:
                    print(f"    TPD: {limits.tpd:,}")
                if limits.itpm:
                    print(f"    Input TPM: {limits.itpm:,}")
                if limits.otpm:
                    print(f"    Output TPM: {limits.otpm:,}")
        else:
            print("  (No rate limiters specified)")

    def calculate_price(self):
        """Calculate price from token usage."""
        self.print_header("CALCULATE PRICE")
        providers = self.pricing.list_providers()

        if not providers:
            print("No providers found.")
            input("Press Enter to continue...")
            return

        # Select provider
        print("Available providers:")
        provider_list = list(providers.items())
        for i, (provider_id, _) in enumerate(provider_list, 1):
            print(f"{i}. {provider_id}")

        try:
            p_choice = int(input("\nSelect provider (number): "))
            if not (1 <= p_choice <= len(provider_list)):
                print("Invalid selection.")
                input("Press Enter to continue...")
                return

            provider_id, provider = provider_list[p_choice - 1]

            if not provider.models:
                print("This provider has no models.")
                input("Press Enter to continue...")
                return

            # Select model
            print(f"\nModels in {provider_id}:")
            model_list = list(provider.models.items())
            for i, (model_id, _) in enumerate(model_list, 1):
                print(f"{i}. {model_id}")

            m_choice = int(input("\nSelect model (number): "))
            if not (1 <= m_choice <= len(model_list)):
                print("Invalid selection.")
                input("Press Enter to continue...")
                return

            model_id, model = model_list[m_choice - 1]

            # Get token counts
            input_tokens = int(input(f"\nInput tokens (0-999999999): "))
            output_tokens = int(input(f"Output tokens (0-999999999): "))

            # Optional: cache tokens
            cache_read = input("Cache read tokens (leave empty for 0): ")
            cache_write = input("Cache write tokens (leave empty for 0): ")

            cache_read_tokens = int(cache_read) if cache_read else 0
            cache_write_tokens = int(cache_write) if cache_write else 0

            # Calculate
            usage = TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read_tokens,
                cache_write_tokens=cache_write_tokens,
            )

            # Optional: tier selection
            print("\nAvailable tiers:")
            tier_list = list(provider.tiers.items()) if provider.tiers else [("default", None)]
            for i, (tier_id, tier) in enumerate(tier_list, 1):
                tier_name = tier.name if tier else "Default"
                print(f"{i}. {tier_id}: {tier_name}")

            tier_choice = input("\nSelect tier (number, or press Enter for first): ")
            selected_tier = (
                tier_list[int(tier_choice) - 1][0]
                if tier_choice and tier_choice.isdigit()
                else tier_list[0][0]
            )

            result = self.pricing.calculate(
                provider=provider_id, model=model_id, usage=usage, tier=selected_tier
            )

            print(f"\n{'=' * 80}")
            print(f"CALCULATION RESULT")
            print(f"{'=' * 80}")
            print(f"Provider: {provider_id}")
            print(f"Model: {model_id}")
            print(f"Tier: {selected_tier}")
            print()
            print(f"Input tokens:        {usage.input_tokens:>15,}")
            print(f"Output tokens:       {usage.output_tokens:>15,}")
            if usage.cache_read_tokens:
                print(f"Cache read tokens:   {usage.cache_read_tokens:>15,}")
            if usage.cache_write_tokens:
                print(f"Cache write tokens:  {usage.cache_write_tokens:>15,}")
            print()
            print(f"Input cost:          ${result.input_cost:>15.4f}")
            print(f"Output cost:         ${result.output_cost:>15.4f}")
            if result.cache_read_cost:
                print(f"Cache read cost:     ${result.cache_read_cost:>15.4f}")
            if result.cache_write_cost:
                print(f"Cache write cost:    ${result.cache_write_cost:>15.4f}")
            print()
            print(f"TOTAL COST:          ${result.total_cost:>15.4f}")
            print(f"{'=' * 80}")

        except ValueError as e:
            print(f"Error: Invalid input - {e}")

        input("\nPress Enter to continue...")

    def add_provider(self):
        """Add a new provider."""
        self.print_header("ADD PROVIDER")

        try:
            provider_id = input("Provider ID (e.g., 'my-company'): ").strip()
            if not provider_id:
                print("Provider ID cannot be empty.")
                input("Press Enter to continue...")
                return

            name = input("Provider name (e.g., 'My Company'): ").strip()
            if not name:
                print("Provider name cannot be empty.")
                input("Press Enter to continue...")
                return

            description = input("Description (optional): ").strip()
            endpoint = input("API endpoint pattern (optional): ").strip()
            docs_url = input("Documentation URL (optional): ").strip()

            provider = Provider(
                provider_id=provider_id,
                name=name,
                description=description or "",
                api_endpoint_pattern=endpoint or "",
                documentation_url=docs_url or "",
            )

            self.pricing.add_provider(provider)
            print(f"\n✓ Provider '{name}' added successfully!")

        except Exception as e:
            print(f"Error: {e}")

        input("\nPress Enter to continue...")

    def add_model(self):
        """Add a model to a provider."""
        self.print_header("ADD MODEL")
        providers = self.pricing.list_providers()

        if not providers:
            print("No providers found. Please add a provider first.")
            input("Press Enter to continue...")
            return

        # Select provider
        print("Available providers:")
        provider_list = list(providers.items())
        for i, (provider_id, _) in enumerate(provider_list, 1):
            print(f"{i}. {provider_id}")

        try:
            p_choice = int(input("\nSelect provider (number): "))
            if not (1 <= p_choice <= len(provider_list)):
                print("Invalid selection.")
                input("Press Enter to continue...")
                return

            provider_id, _ = provider_list[p_choice - 1]

            # Get model details
            model_id = input("\nModel ID (e.g., 'gpt-4o'): ").strip()
            if not model_id:
                print("Model ID cannot be empty.")
                input("Press Enter to continue...")
                return

            name = input("Model name (e.g., 'GPT-4 Optimized'): ").strip()
            if not name:
                print("Model name cannot be empty.")
                input("Press Enter to continue...")
                return

            description = input("Description (optional): ").strip()
            context_window = input("Context window (tokens, e.g., 128000): ").strip()
            context_window = int(context_window) if context_window else 0

            # Pricing
            print("\nPricing configuration:")
            input_price = input("Input price per 1M tokens: ").strip()
            output_price = input("Output price per 1M tokens: ").strip()

            if not input_price or not output_price:
                print("Input and output prices are required.")
                input("Press Enter to continue...")
                return

            pricing = ModelPrice(
                input_mtok=Decimal(input_price),
                output_mtok=Decimal(output_price),
            )

            # Optional cache pricing
            cache_read = input("Cache read price per 1M tokens (optional): ").strip()
            cache_write = input("Cache write price per 1M tokens (optional): ").strip()

            if cache_read:
                pricing.cache_read_mtok = Decimal(cache_read)
            if cache_write:
                pricing.cache_write_mtok = Decimal(cache_write)

            model = ModelInfo(
                model_id=model_id,
                name=name,
                provider_id=provider_id,
                description=description or "",
                context_window=context_window,
                pricing=pricing,
            )

            self.pricing.add_model(provider_id, model)
            print(f"\n✓ Model '{name}' added to '{provider_id}' successfully!")

        except Exception as e:
            print(f"Error: {e}")

        input("\nPress Enter to continue...")

    def list_snapshots(self):
        """List available snapshots."""
        self.print_header("SNAPSHOTS")
        try:
            snapshots = self.pricing._snapshot_manager.list_snapshots()

            if not snapshots:
                print("No snapshots found.")
            else:
                print(f"Found {len(snapshots)} snapshots:\n")
                for snapshot in snapshots:
                    print(f"  • {snapshot.filename}")
                    print(f"      Created: {snapshot.timestamp}")
                    print(f"      Providers: {snapshot.provider_count}")
                    print(f"      Models: {snapshot.model_count}")
                    print()
        except Exception as e:
            print(f"Error: {e}")

        input("Press Enter to continue...")

    def store_snapshot(self):
        """Store a snapshot."""
        self.print_header("STORE SNAPSHOT")
        try:
            snapshot_info = self.pricing.store_snapshot()
            print(f"✓ Snapshot stored successfully!")
            print(f"\nFilename: {snapshot_info.filename}")
            print(f"Timestamp: {snapshot_info.timestamp}")
            print(f"Providers: {snapshot_info.provider_count}")
            print(f"Models: {snapshot_info.model_count}")
        except Exception as e:
            print(f"Error: {e}")

        input("\nPress Enter to continue...")

    def show_statistics(self):
        """Show database statistics."""
        self.print_header("DATABASE STATISTICS")
        providers = self.pricing.list_providers()

        print(f"Total Providers: {len(providers)}")
        print(f"Total Models: {self.pricing.model_count}")

        if providers:
            print(f"\nProviders:")
            for provider_id, provider in sorted(providers.items()):
                print(
                    f"  • {provider_id}: {len(provider.models)} models, "
                    f"{len(provider.tiers)} tiers"
                )

        input("\nPress Enter to continue...")

    @staticmethod
    def _format_price_value(price):
        """Format a price value for display."""
        if price is None:
            return "-"

        if isinstance(price, TieredPrice):
            result = f"${price.base:.4f}"
            if price.tiers:
                tier_parts = []
                for tier in price.tiers:
                    tier_parts.append(f"${tier.price:.4f} after {tier.start:,} tokens")
                result += f" (then {', '.join(tier_parts)})"
            return result
        elif isinstance(price, Decimal):
            return f"${price:.4f}" if price != 0 else "Free"
        else:
            return f"${price:.4f}" if price != 0 else "Free"

    def run(self):
        """Run the main CLI loop."""
        while True:
            self.print_menu()
            choice = input("Select option (0-9): ").strip()

            if choice == "1":
                self.list_providers_and_models()
            elif choice == "2":
                self.view_provider_details()
            elif choice == "3":
                self.view_model_details()
            elif choice == "4":
                self.calculate_price()
            elif choice == "5":
                self.add_provider()
            elif choice == "6":
                self.add_model()
            elif choice == "7":
                self.list_snapshots()
            elif choice == "8":
                self.store_snapshot()
            elif choice == "9":
                self.show_statistics()
            elif choice == "0":
                print("\nGoodbye!")
                sys.exit(0)
            else:
                print("Invalid option. Please try again.")
                input("Press Enter to continue...")


def main():
    """Main entry point."""
    try:
        app = CLIApp()
        app.run()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
