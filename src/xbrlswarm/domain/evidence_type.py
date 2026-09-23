from __future__ import annotations

from enum import StrEnum


class EvidenceType(StrEnum):
    """證據所描述的 artifact 或事件種類。"""

    XBRL_DOCUMENT = "xbrl_document"
    FINANCIAL_REPORT_DOCUMENT = "financial_report_document"
    MATERIAL_ANNOUNCEMENT = "material_announcement"
    SEARCH_MIRROR = "search_mirror"
    MANUAL_REVIEW = "manual_review"

    @classmethod
    def parse(cls, value: str) -> "EvidenceType":
        try:
            return cls(value.lower())
        except ValueError as exc:
            allowed = ", ".join(item.value for item in cls)
            raise ValueError(f"無效的證據類型 {value!r}；應為以下其中之一：{allowed}") from exc
