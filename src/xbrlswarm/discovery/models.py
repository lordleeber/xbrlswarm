from __future__ import annotations

import re
from dataclasses import dataclass

from xbrlswarm.domain import ReportPeriod

_STOCK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True, slots=True)
class DiscoveryCase:
    stock_id: str
    company_name: str
    fiscal_year: int
    report_period: ReportPeriod

    def __post_init__(self) -> None:
        if not _STOCK_ID.fullmatch(self.stock_id):
            raise ValueError("stock_id 只能包含英文字母、數字、底線或連字號")
        if not self.company_name.strip():
            raise ValueError("company_name 不得為空白")
        if self.fiscal_year < 1900 or self.fiscal_year > 2200:
            raise ValueError("fiscal_year 超出目前支援的來源探索範圍")

    @property
    def key(self) -> str:
        return f"{self.stock_id}-{self.fiscal_year}-{self.report_period.value}"
