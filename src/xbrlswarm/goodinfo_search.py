"""Source-backed, narrowly scoped Goodinfo announcement search dates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .domain import (
    PublicationWindow,
    PublicationWindowQuery,
    PublicationWindowRuleProvider,
    ReportPeriod,
    VersionedPublicationRule,
    VersionedPublicationRuleProvider,
    calendar_year_period_end,
    expected_publication_window,
)
from .goodinfo_list import AnnouncementListQuery

GENERAL_ARTICLE_36 = "securities_act_article_36_general"
_LAW_2023 = (
    "https://twse-regulation.twse.com.tw/TW/law/DAT06.aspx"
    "?FLCODE=FL007009&FLDATE=20230510&LSER=001"
)
_LAW_2024 = (
    "https://twse-regulation.twse.com.tw/TW/law/DAT07.aspx"
    "?FLCODE=FE396664&LDATE=20240807&LSID=FL007009&TY=E"
)


def _article_36_dates(query: PublicationWindowQuery) -> tuple[date, date]:
    period_end = calendar_year_period_end(query.fiscal_year, query.report_period)
    start = period_end + timedelta(days=1)
    if query.report_period is ReportPeriod.FY:
        deadline = date(query.fiscal_year + 1, 3, 31)
    else:
        deadline = period_end + timedelta(days=45)
    return start, deadline


def _verified_2024_provider() -> VersionedPublicationRuleProvider:
    rules = (
        VersionedPublicationRule(
            valid_from=date(2024, 1, 1),
            valid_to=date(2024, 12, 31),
            rule_id=f"TW-SEA36-2024-{period.value}",
            report_period=period,
            company_class=GENERAL_ARTICLE_36,
            fiscal_calendar="calendar_year",
            source_ref=_LAW_2023 if period in (ReportPeriod.Q1, ReportPeriod.Q2) else _LAW_2024,
            window_for=_article_36_dates,
        )
        for period in ReportPeriod
    )
    return VersionedPublicationRuleProvider(
        rules,
        effective_date_for_query=lambda query: calendar_year_period_end(
            query.fiscal_year, query.report_period
        ),
    )


VERIFIED_2024_RULES = _verified_2024_provider()


@dataclass(frozen=True, slots=True)
class GoodinfoSearchPlan:
    query: AnnouncementListQuery
    publication_window: PublicationWindow


def goodinfo_search_plan(
    stock_id: str,
    fiscal_year: int,
    report_period: ReportPeriod | str,
    company_class: str,
    fiscal_calendar: str,
    *,
    rule_provider: PublicationWindowRuleProvider | None = None,
) -> GoodinfoSearchPlan:
    """Make one raw list query from an applicable legal publication window.

    The built-in provider covers only ordinary Article 36 cases for fiscal
    2024. Callers must establish company class and fiscal calendar separately.
    An empty result is never proof that a report or announcement is absent.
    """

    window = expected_publication_window(
        fiscal_year, report_period, company_class, fiscal_calendar,
        rule_provider=VERIFIED_2024_RULES if rule_provider is None else rule_provider,
    )
    query = AnnouncementListQuery(stock_id, window.earliest_date, window.latest_date)
    return GoodinfoSearchPlan(query, window)
