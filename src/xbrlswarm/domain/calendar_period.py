"""Quarter and annual period ends for confirmed calendar-year fiscal calendars."""

from datetime import date

from .report_period import ReportPeriod


_PERIOD_END_MONTH_DAY = {
    ReportPeriod.Q1: (3, 31),
    ReportPeriod.Q2: (6, 30),
    ReportPeriod.Q3: (9, 30),
    ReportPeriod.FY: (12, 31),
}


def calendar_year_period_end(
    fiscal_year: int, report_period: ReportPeriod | str
) -> date:
    """Return a calendar-year period end, not a source-claimed evidence date.

    Call only when the company's fiscal calendar is independently known to
    end on December 31. Publication deadlines are a separate rule.
    """
    if isinstance(fiscal_year, bool) or not isinstance(fiscal_year, int):
        raise ValueError("fiscal_year 必須是 1 到 9999 的整數")
    if not 1 <= fiscal_year <= 9999:
        raise ValueError("fiscal_year 必須是 1 到 9999 的整數")
    if not isinstance(report_period, str):
        raise ValueError("report_period 必須是 Q1、Q2、Q3 或 FY")

    period = ReportPeriod.parse(report_period)
    month, day = _PERIOD_END_MONTH_DAY[period]
    return date(fiscal_year, month, day)
