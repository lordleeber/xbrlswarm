import json
import sqlite3
from pathlib import Path

import pytest

from xbrlswarm.domain import expected_publication_window


ASSESSMENT = Path("discovery/fiscal_calendar_research.json")
DECISION = Path("docs/fiscal-calendar-research.md")
ACCEPTANCE = Path("docs/step-21-acceptance.md")
OBSERVATIONS = Path("discovery/mops_field_observations.json")


def test_official_source_capabilities_are_not_confused_with_company_coverage() -> None:
    assessment = json.loads(ASSESSMENT.read_text(encoding="utf-8"))

    assert assessment["schema_version"] == 1
    assert assessment["reviewed_on"] == "2026-09-24"
    capabilities = assessment["verified_capabilities"]
    assert {item["claim"] for item in capabilities} == {
        "non_calendar_years_supported_in_xbrl_tool",
        "mops_company_basic_data_has_accounting_year_setting",
        "accounting_year_changes_are_disclosable_events",
    }
    assert all(item["source_url"].startswith("https://") for item in capabilities)
    assert all(
        "twse.com.tw" in item["source_url"] for item in capabilities
    )
    assert assessment["verified_non_calendar_companies"] == []
    assert assessment["verified_company_calendar_changes"] == []


def test_three_research_questions_remain_explicitly_unresolved() -> None:
    assessment = json.loads(ASSESSMENT.read_text(encoding="utf-8"))

    assert assessment["questions"] == {
        "which_companies_are_not_december_31_year_end": "not_verified",
        "which_companies_changed_year_end_historically": "not_verified",
        "stable_public_historical_batch_source": "not_verified",
    }
    assert assessment["mops_basic_data_access_test"]["result"] == "security_block_page"
    assert assessment["mops_basic_data_access_test"]["is_source_evidence"] is False
    assert assessment["gate"] == {
        "all_market_task_generation": "defer",
        "non_calendar_year_task_generation": "defer",
        "calendar_year_task_generation": "require_company_period_evidence",
        "fiscal_year_end_schema": "defer_to_step_22",
    }


def test_fixed_mops_fixtures_do_not_establish_all_market_calendar_coverage() -> None:
    observations = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
    stock_ids = {
        case["facts"]["tifrs-notes:CompanyID"] for case in observations["cases"]
    }
    assert stock_ids == {"2330", "6147", "4542"}
    assert len(observations["cases"]) == 12


def test_existing_runtime_still_rejects_unmodeled_fiscal_calendar() -> None:
    with pytest.raises(ValueError, match="fiscal_calendar"):
        expected_publication_window(
            fiscal_year=2024,
            report_period="Q1",
            company_class="test_class",
            fiscal_calendar="non_calendar_year",
        )


def test_research_does_not_create_unverified_production_column() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        for path in sorted(Path("migrations").glob("*.sql")):
            connection.executescript(path.read_text(encoding="utf-8"))
        columns = {row[1] for row in connection.execute("PRAGMA table_info(evidence)")}
    finally:
        connection.close()
    assert "fiscal_year_end" not in columns


def test_decision_and_acceptance_keep_unknown_distinct_from_absent() -> None:
    decision = DECISION.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE.read_text(encoding="utf-8")

    assert "不是不存在" in decision
    assert "12 份" in decision
    assert "Step-22" in decision
    assert "不需要 migration" in acceptance
