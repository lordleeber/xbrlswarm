"""Infrastructure failures that must retry on the current engine."""

from enum import StrEnum


class RetryableFailure(StrEnum):
    RATE_LIMITED = "rate_limited"
    TRANSPORT_ERROR = "transport_error"
    TEMPORARY_ERROR = "temporary_error"
