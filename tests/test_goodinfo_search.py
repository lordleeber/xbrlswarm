"""Legal-scope regressions for Step-35 Goodinfo search dates."""

import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from xbrlswarm.domain import PublicationRuleUnavailable, PublicationWindow
from xbrlswarm.goodinfo_search import (
    GENERAL_ARTICLE_36,
    VERIFIED_2024_RULES,
    goodinfo_search_plan,
)


@pytest.mark.parametrize("period,start,end", [
    ("Q1", date(2024, 4, 1), date(2024, 5, 15)),
    ("Q2", date(2024, 7, 1), date(2024, 8, 14)),
    ("Q3", date(2024, 10, 1), date(2024, 11, 14)),
    ("FY", date(2025, 1, 1), date(2025, 3, 31)),
])
def test_2024_article_36_windows_feed_exact_goodinfo_query(period, start, end) -> None:
    plan = goodinfo_search_plan(
        "0050", 2024, period, GENERAL_ARTICLE_36, "calendar_year"
    )
    assert (plan.query.start_date, plan.query.end_date) == (start, end)
    assert plan.publication_window == PublicationWindow(
        start, end, f"TW-SEA36-2024-{period}"
    )
    assert parse_qs(urlsplit(plan.query.url).query) == {
        "STOCK_ID": ["0050"],
        "START_DT": [start.strftime("%Y/%m/%d")],
        "END_DT": [end.strftime("%Y/%m/%d")],
    }


@pytest.mark.parametrize("year,company_class,calendar", [
    (2023, GENERAL_ARTICLE_36, "calendar_year"),
    (2025, GENERAL_ARTICLE_36, "calendar_year"),
    (2024, "first_listed", "calendar_year"),
    (2024, "second_listed", "calendar_year"),
    (2024, "financial", "calendar_year"),
])
def test_no_builtin_rule_outside_verified_scope(year, company_class, calendar) -> None:
    with pytest.raises(PublicationRuleUnavailable):
        goodinfo_search_plan("2330", year, "Q2", company_class, calendar)


def test_non_calendar_year_and_invalid_period_are_rejected() -> None:
    with pytest.raises(ValueError, match="fiscal_calendar"):
        goodinfo_search_plan("2330", 2024, "Q2", GENERAL_ARTICLE_36, "unknown")
    with pytest.raises(ValueError, match="Q4"):
        goodinfo_search_plan("2330", 2024, "Q4", GENERAL_ARTICLE_36, "calendar_year")


def test_explicit_verified_provider_can_extend_to_another_year() -> None:
    class Provider:
        def resolve(self, query):
            assert query.fiscal_year == 2025
            return PublicationWindow(date(2025, 4, 1), date(2025, 5, 15), "OTHER-VERIFIED")

    plan = goodinfo_search_plan(
        "2330", 2025, "Q1", GENERAL_ARTICLE_36, "calendar_year",
        rule_provider=Provider(),
    )
    assert plan.publication_window.rule_id == "OTHER-VERIFIED"
    assert plan.query.end_date == date(2025, 5, 15)


def test_machine_readable_scope_and_law_sources() -> None:
    contract = json.loads(Path("contracts/goodinfo-search-window.json").read_text())
    assert contract["built_in_fiscal_years"] == [2024]
    assert contract["built_in_company_class"] == GENERAL_ARTICLE_36
    assert contract["empty_list_means_absence"] is False
    assert contract["includes_late_amendments_or_extensions"] is False
    assert all(url.startswith("https://twse-regulation.twse.com.tw/")
               for url in contract["source_refs"].values())
    assert {rule.rule_id for rule in VERIFIED_2024_RULES.rules} == {
        f"TW-SEA36-2024-{period}" for period in ("Q1", "Q2", "Q3", "FY")
    }
    for rule in VERIFIED_2024_RULES.rules:
        source_key = "Q1_Q2" if rule.report_period in ("Q1", "Q2") else "Q3_FY"
        assert rule.source_ref == contract["source_refs"][source_key]
        assert (rule.valid_from, rule.valid_to) == (date(2024, 1, 1), date(2024, 12, 31))
