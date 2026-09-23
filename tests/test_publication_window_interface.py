import json
from datetime import date, datetime
from pathlib import Path

import pytest


CONTRACT = Path("contracts/publication-window-interface.json")
DECISION = Path("docs/publication-window-interface.md")
ACCEPTANCE = Path("docs/step-19-acceptance.md")


def test_provider_receives_all_four_inputs_and_returns_named_window() -> None:
    from xbrlswarm.domain import (
        PublicationWindow,
        ReportPeriod,
        expected_publication_window,
    )

    class TestOnlyProvider:
        def __init__(self) -> None:
            self.queries = []

        def resolve(self, query):
            self.queries.append(query)
            return PublicationWindow(
                earliest_date=date(2040, 4, 1),
                latest_date=date(2040, 4, 2),
                rule_id="TEST-ONLY-NOT-LAW",
            )

    provider = TestOnlyProvider()
    result = expected_publication_window(
        fiscal_year=2040,
        report_period=ReportPeriod.Q1,
        company_class="test_class",
        fiscal_calendar="calendar_year",
        rule_provider=provider,
    )

    assert result == PublicationWindow(
        earliest_date=date(2040, 4, 1),
        latest_date=date(2040, 4, 2),
        rule_id="TEST-ONLY-NOT-LAW",
    )
    assert len(provider.queries) == 1
    assert vars_from_query(provider.queries[0]) == {
        "fiscal_year": 2040,
        "report_period": ReportPeriod.Q1,
        "company_class": "test_class",
        "fiscal_calendar": "calendar_year",
    }


def vars_from_query(query) -> dict:
    return {
        "fiscal_year": query.fiscal_year,
        "report_period": query.report_period,
        "company_class": query.company_class,
        "fiscal_calendar": query.fiscal_calendar,
    }


def test_no_provider_or_no_matching_rule_never_guesses_a_window() -> None:
    from xbrlswarm.domain import PublicationRuleUnavailable, expected_publication_window

    args = {
        "fiscal_year": 2040,
        "report_period": "Q1",
        "company_class": "test_class",
        "fiscal_calendar": "calendar_year",
    }
    with pytest.raises(PublicationRuleUnavailable):
        expected_publication_window(**args)

    class EmptyProvider:
        def resolve(self, query):
            return None

    with pytest.raises(PublicationRuleUnavailable):
        expected_publication_window(**args, rule_provider=EmptyProvider())


@pytest.mark.parametrize(
    "change,match",
    [
        ({"fiscal_year": 0}, "fiscal_year"),
        ({"report_period": "Q4"}, "Q4"),
        ({"company_class": "  "}, "company_class"),
        ({"fiscal_calendar": "non_calendar_year"}, "fiscal_calendar"),
    ],
)
def test_unsupported_inputs_are_rejected_before_rule_lookup(change, match) -> None:
    from xbrlswarm.domain import expected_publication_window

    class NeverCalledProvider:
        def resolve(self, query):
            raise AssertionError("unsupported inputs must not reach the provider")

    args = {
        "fiscal_year": 2040,
        "report_period": "Q1",
        "company_class": "test_class",
        "fiscal_calendar": "calendar_year",
    }
    with pytest.raises(ValueError, match=match):
        expected_publication_window(
            **{**args, **change}, rule_provider=NeverCalledProvider()
        )


@pytest.mark.parametrize(
    "earliest,latest,rule_id",
    [
        (date(2040, 5, 1), date(2040, 4, 1), "TEST-ONLY"),
        (date(2040, 4, 1), date(2040, 5, 1), ""),
        (datetime(2040, 4, 1), date(2040, 5, 1), "TEST-ONLY"),
    ],
)
def test_window_rejects_invalid_or_unnamed_rules(earliest, latest, rule_id) -> None:
    from xbrlswarm.domain import PublicationWindow

    with pytest.raises(ValueError):
        PublicationWindow(earliest, latest, rule_id)


def test_contract_defines_interface_without_inventing_law() -> None:
    assert json.loads(CONTRACT.read_text(encoding="utf-8")) == {
        "contract": "publication_window_interface",
        "version": 1,
        "function": "expected_publication_window",
        "inputs": [
            "fiscal_year",
            "report_period",
            "company_class",
            "fiscal_calendar",
        ],
        "output": ["earliest_date", "latest_date", "rule_id"],
        "rule_provider": "explicit_injection_required",
        "missing_rule": "raise_publication_rule_unavailable",
        "supported_fiscal_calendar": ["calendar_year"],
        "historical_rule_versioning_deferred_to_step": 20,
        "non_calendar_year_research_deferred_to_step": 21,
    }


def test_docs_keep_rule_interface_separate_from_verified_legal_dates() -> None:
    decision = DECISION.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE.read_text(encoding="utf-8")

    assert "TEST-ONLY-NOT-LAW" in decision
    assert "不需要 migration" in acceptance
    assert "Step-20" in decision
