import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from xbrlswarm.domain import ReportPeriod


CONTRACT = Path("contracts/calendar-year-period-boundaries.json")
DECISION = Path("docs/calendar-year-period-boundaries.md")
ACCEPTANCE = Path("docs/step-18-acceptance.md")


@pytest.mark.parametrize(
    "period,month,day",
    [
        (ReportPeriod.Q1, 3, 31),
        (ReportPeriod.Q2, 6, 30),
        (ReportPeriod.Q3, 9, 30),
        (ReportPeriod.FY, 12, 31),
    ],
)
@pytest.mark.parametrize("year", [2023, 2024, 2025])
def test_calendar_year_period_end_mapping(
    year: int, period: ReportPeriod, month: int, day: int
) -> None:
    from xbrlswarm.domain import calendar_year_period_end

    assert calendar_year_period_end(year, period) == date(year, month, day)


def test_fy_is_not_q4_and_source_alias_is_not_accepted() -> None:
    from xbrlswarm.domain import calendar_year_period_end

    assert calendar_year_period_end(2024, ReportPeriod.FY) == date(2024, 12, 31)
    with pytest.raises(ValueError, match="Q4"):
        calendar_year_period_end(2024, "Q4")


@pytest.mark.parametrize("year", [0, -1, 10000, True, "2024"])
def test_invalid_fiscal_year_is_rejected(year: object) -> None:
    from xbrlswarm.domain import calendar_year_period_end

    with pytest.raises(ValueError, match="fiscal_year"):
        calendar_year_period_end(year, ReportPeriod.Q1)


def test_contract_limits_mapping_to_calendar_year_and_period_ends() -> None:
    assert json.loads(CONTRACT.read_text(encoding="utf-8")) == {
        "contract": "calendar_year_period_boundaries",
        "version": 1,
        "fiscal_calendar": "calendar_year",
        "result": "period_end_date",
        "period_ends": {
            "Q1": "03-31",
            "Q2": "06-30",
            "Q3": "09-30",
            "FY": "12-31",
        },
        "not_a_source_backed_evidence_field": True,
        "publication_deadline_deferred_to_step": 19,
        "non_calendar_year_deferred_to_step": 21,
    }


def test_period_boundary_does_not_bypass_evidence_source_gate() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        for path in sorted(Path("migrations").glob("*.sql")):
            connection.executescript(path.read_text(encoding="utf-8"))
        columns = {row[1] for row in connection.execute("PRAGMA table_info(evidence)")}
    finally:
        connection.close()
    assert "period_end" not in columns
    assert "period_start" not in columns


def test_step18_documents_scope_and_no_migration() -> None:
    decision = DECISION.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE.read_text(encoding="utf-8")

    assert "曆年制" in decision
    assert "FY != Q4" in decision
    assert "evidence.period_end" in decision
    assert "不需要 migration" in acceptance
