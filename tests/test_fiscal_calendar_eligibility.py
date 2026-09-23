import json
import sqlite3
from pathlib import Path

import pytest

from xbrlswarm.domain import expected_publication_window


CONTRACT = Path("contracts/fiscal-calendar-eligibility.json")
ASSESSMENT = Path("discovery/fiscal_calendar_research.json")
DECISION = Path("docs/fiscal-calendar-eligibility.md")
ACCEPTANCE = Path("docs/step-22-acceptance.md")


def test_step22_selects_calendar_year_only_when_research_is_unverified() -> None:
    assessment = json.loads(ASSESSMENT.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert assessment["questions"]["stable_public_historical_batch_source"] == "not_verified"
    assert assessment["verified_non_calendar_companies"] == []
    assert contract == {
        "contract": "fiscal_calendar_eligibility",
        "version": 1,
        "research_assessment": "discovery/fiscal_calendar_research.json",
        "first_version_scope": "verified_calendar_year_companies_only",
        "company_period_source_evidence": "required_before_scheduling",
        "supported_fiscal_calendar": ["calendar_year"],
        "unknown_or_unverified": "unsupported_do_not_default",
        "non_calendar_year": "unsupported_until_source_backed_model",
        "all_market_task_generation": "defer",
        "fiscal_year_end_production_column": "not_added",
    }


@pytest.mark.parametrize("fiscal_calendar", [None, "", "unknown", "non_calendar_year", "12/31"])
def test_unverified_or_unmodeled_calendar_never_reaches_rule_provider(
    fiscal_calendar: object,
) -> None:
    class NeverCalledProvider:
        def resolve(self, query):
            raise AssertionError("unsupported calendar reached rule provider")

    with pytest.raises(ValueError, match="fiscal_calendar"):
        expected_publication_window(
            fiscal_year=2024,
            report_period="Q1",
            company_class="test_class",
            fiscal_calendar=fiscal_calendar,
            rule_provider=NeverCalledProvider(),
        )


def test_no_unverified_fiscal_year_end_column_is_added() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        for path in sorted(Path("migrations").glob("*.sql")):
            connection.executescript(path.read_text(encoding="utf-8"))
        columns = {row[1] for row in connection.execute("PRAGMA table_info(evidence)")}
    finally:
        connection.close()

    assert "fiscal_year_end" not in columns


def test_scope_and_source_evidence_gate_are_documented() -> None:
    decision = DECISION.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE.read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "calendar-year companies only" in decision
    assert "公司及歷史期間" in decision
    assert "未知不等於 12/31" in decision
    assert "不需要 migration" in acceptance
    assert "Step-22" in readme
