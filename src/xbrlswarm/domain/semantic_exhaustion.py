"""Outcomes that exhaust the current engine without a trustworthy answer."""

from enum import StrEnum


class SemanticExhaustion(StrEnum):
    NOT_FOUND = "not_found"
    REJECTED = "rejected"
