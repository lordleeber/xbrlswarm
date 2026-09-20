from __future__ import annotations

from .models import DiscoveryCase, ReportPeriod

_COMPANIES = (
    ("2330", "台積電"),
    ("6147", "頎邦"),
    ("4542", "科嶠"),
)

DISCOVERY_CASES: tuple[DiscoveryCase, ...] = tuple(
    DiscoveryCase(stock_id, company_name, 2024, period)
    for stock_id, company_name in _COMPANIES
    for period in ReportPeriod
)


def find_case(stock_id: str, fiscal_year: int, report_period: ReportPeriod) -> DiscoveryCase | None:
    for case in DISCOVERY_CASES:
        if (
            case.stock_id == stock_id
            and case.fiscal_year == fiscal_year
            and case.report_period is report_period
        ):
            return case
    return None
