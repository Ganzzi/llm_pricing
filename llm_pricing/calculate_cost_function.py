from typing import Optional, Union
from .llm_pricing import LLMPricing
from .engine import TokenUsage, CostBreakdown


def calculate_cost(
    provider: str,
    model: str,
    usage: Optional[TokenUsage] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    tier: Optional[str] = None,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
) -> CostBreakdown:
    """Quick convenience function to calculate cost.

    Creates a temporary LLMPricing instance and calculates cost.
    For repeated calculations, use LLMPricing class directly.

    Args:
        provider: Provider ID (e.g., "anthropic")
        model: Model ID (e.g., "claude-sonnet-4-20250514")
        usage: TokenUsage object. If not provided, input_tokens and output_tokens must be specified.
        input_tokens: Number of input tokens (if usage not provided)
        output_tokens: Number of output tokens (if usage not provided)
        tier: Optional tier (defaults to "default")
        cache_read_tokens: Cache read tokens (optional)
        cache_creation_tokens: Cache creation tokens (optional)

    Returns:
        CostBreakdown with cost information

    Example:
        ```python
        from llm_pricing import calculate_cost, TokenUsage

        # Using TokenUsage object
        usage = TokenUsage(input_tokens=100000, output_tokens=50000)
        result = calculate_cost(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            usage=usage,
        )

        # Or using direct token counts
        result = calculate_cost(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            input_tokens=100000,
            output_tokens=50000,
        )
        print(f"Cost: ${result.total_cost}")
        ```
    """
    pricing = LLMPricing()

    # Create TokenUsage if not provided
    if usage is None:
        if input_tokens is None or output_tokens is None:
            raise ValueError(
                "Either 'usage' or both 'input_tokens' and 'output_tokens' must be provided"
            )
        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
        )

    return pricing.calculate(
        provider=provider,
        model=model,
        usage=usage,
        tier=tier,
    )
