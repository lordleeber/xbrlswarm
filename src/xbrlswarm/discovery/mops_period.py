from __future__ import annotations

from xbrlswarm.domain import ReportPeriod

MOPS_QUARTER_NUMBER_TO_REPORT_PERIOD = {
    1: ReportPeriod.Q1,
    2: ReportPeriod.Q2,
    3: ReportPeriod.Q3,
    4: ReportPeriod.FY,
}

_MOPS_SOURCE_PERIOD_TO_REPORT_PERIOD = {
    **{str(quarter): period for quarter, period in MOPS_QUARTER_NUMBER_TO_REPORT_PERIOD.items()},
    **{
        f"Q{quarter}": period
        for quarter, period in MOPS_QUARTER_NUMBER_TO_REPORT_PERIOD.items()
    },
}
_MOPS_QUARTER_NUMBER_BY_REPORT_PERIOD = {
    period: quarter for quarter, period in MOPS_QUARTER_NUMBER_TO_REPORT_PERIOD.items()
}


def normalize_mops_report_period(source_value: str | int) -> ReportPeriod:
    """將已驗證的 MOPS quarter 值轉為內部報告期別。"""

    normalized = str(source_value).upper()
    try:
        return _MOPS_SOURCE_PERIOD_TO_REPORT_PERIOD[normalized]
    except KeyError as exc:
        raise ValueError(f"無法識別的 MOPS 報告期別：{source_value!r}") from exc


def mops_quarter_number(report_period: ReportPeriod) -> int:
    """回傳內部期別在已驗證 MOPS quarter 欄位中的數值。"""

    return _MOPS_QUARTER_NUMBER_BY_REPORT_PERIOD[report_period]
