"""Source-backed revision classifications, distinct from evidence identity."""

from enum import StrEnum


class RevisionKind(StrEnum):
    ORIGINAL = "original"
    AMENDMENT = "amendment"
    SUPPLEMENTAL = "supplemental"
    UNKNOWN = "unknown"
