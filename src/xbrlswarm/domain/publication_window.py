"""Interface for evidence-backed publication-window rules, without rule data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from .calendar_period import calendar_year_period_end
from .report_period import ReportPeriod


class PublicationRuleUnavailable(LookupError):
    """No verified publication rule is available for this query."""


@dataclass(frozen=True, slots=True)
class PublicationWindowQuery:
    fiscal_year: int
    report_period: ReportPeriod
    company_class: str
    fiscal_calendar: str


@dataclass(frozen=True, slots=True)
class PublicationWindow:
    earliest_date: date
    latest_date: date
    rule_id: str

    def __post_init__(self) -> None:
        if type(self.earliest_date) is not date or type(self.latest_date) is not date:
            raise ValueError("publication window 必須使用日期，不得使用時間")
        if self.earliest_date > self.latest_date:
            raise ValueError("earliest_date 不得晚於 latest_date")
        if not isinstance(self.rule_id, str) or not self.rule_id.strip():
            raise ValueError("rule_id 不得為空白")


class PublicationWindowRuleProvider(Protocol):
    """Resolve a query against separately verified, eventually versioned rules."""

    def resolve(self, query: PublicationWindowQuery) -> PublicationWindow | None: ...


def expected_publication_window(
    fiscal_year: int,
    report_period: ReportPeriod | str,
    company_class: str,
    fiscal_calendar: str,
    *,
    rule_provider: PublicationWindowRuleProvider | None = None,
) -> PublicationWindow:
    """Return a provider-backed window or refuse to invent a legal deadline."""
    if fiscal_calendar != "calendar_year":
        raise ValueError("unsupported fiscal_calendar: only calendar_year is modeled")
    if not isinstance(company_class, str) or not company_class.strip():
        raise ValueError("company_class 不得為空白")

    # Reuse Step-18's strict fiscal-year and period validation, but do not
    # derive a publication deadline from its period-end date.
    calendar_year_period_end(fiscal_year, report_period)
    period = ReportPeriod.parse(report_period)
    query = PublicationWindowQuery(
        fiscal_year=fiscal_year,
        report_period=period,
        company_class=company_class,
        fiscal_calendar=fiscal_calendar,
    )
    if rule_provider is None:
        raise PublicationRuleUnavailable("no verified publication rule provider")
    window = rule_provider.resolve(query)
    if window is None:
        raise PublicationRuleUnavailable("no verified publication rule for query")
    if not isinstance(window, PublicationWindow):
        raise TypeError("rule provider must return PublicationWindow or None")
    return window
