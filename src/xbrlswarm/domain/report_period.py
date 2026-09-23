from __future__ import annotations

from enum import StrEnum


class ReportPeriod(StrEnum):
    """財務報告的內部標準期別；FY 是年度報告，不是 Q4。"""

    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    FY = "FY"

    @classmethod
    def parse(cls, value: str) -> "ReportPeriod":
        try:
            return cls(value.upper())
        except ValueError as exc:
            allowed = ", ".join(item.value for item in cls)
            raise ValueError(f"無效的報告期別 {value!r}；應為以下其中之一：{allowed}") from exc
