"""Custom exceptions for the LLM pricing package."""


class LLMPricingError(Exception):
    """Base exception for all pricing errors."""

    pass


class StorageError(LLMPricingError):
    """Error in storage operations."""

    pass


class StorageNotFoundError(StorageError):
    """Storage file not found."""

    pass


class PricingError(LLMPricingError):
    """Error in pricing calculations."""

    pass


class ValidationError(LLMPricingError):
    """Data validation error."""

    pass
