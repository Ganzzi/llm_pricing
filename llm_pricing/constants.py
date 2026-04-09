"""Constants and enums for the LLM pricing package."""

from enum import Enum


class RateLimiterType(str, Enum):
    """Types of rate limiters."""

    RPM = "rpm"  # Requests per minute
    RPD = "rpd"  # Requests per day
    TPM = "tpm"  # Tokens per minute (total)
    TPD = "tpd"  # Tokens per day
    ITPM = "itpm"  # Input tokens per minute
    OTPM = "otpm"  # Output tokens per minute


# Default tier ID
DEFAULT_TIER = "default"

# Schema version
SCHEMA_VERSION = "1.0"
