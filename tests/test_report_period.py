import json
from pathlib import Path

import pytest

from xbrlswarm.discovery.models import ReportPeriod as DiscoveryReportPeriod
from xbrlswarm.discovery.mops_period import (
    mops_quarter_number,
    normalize_mops_report_period,
)
from xbrlswarm.domain import ReportPeriod


FIXTURE_PATH = Path("tests/fixtures/domain/report-period-normalization.json")
OBSERVATIONS_PATH = Path("discovery/mops_field_observations.json")
DECISION_PATH = Path("docs/report-period.md")
ACCEPTANCE_PATH = Path("docs/step-6-acceptance.md")


def test_internal_report_period_has_only_four_canonical_values() -> None:
    assert tuple(period.value for period in ReportPeriod) == ("Q1", "Q2", "Q3", "FY")
    assert DiscoveryReportPeriod is ReportPeriod


def test_internal_parser_does_not_treat_q4_as_a_domain_period() -> None:
    assert ReportPeriod.parse("q1") is ReportPeriod.Q1
    assert ReportPeriod.parse("FY") is ReportPeriod.FY

    with pytest.raises(ValueError, match="Q1, Q2, Q3, FY"):
        ReportPeriod.parse("Q4")


def test_mops_source_period_fixture_normalizes_q4_to_fy() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert fixture["source"] == "mops-xbrl-quarter"
    for case in fixture["cases"]:
        expected = ReportPeriod(case["report_period"])
        assert normalize_mops_report_period(case["source_value"]) is expected
        assert normalize_mops_report_period(case["source_label"]) is expected
        assert mops_quarter_number(expected) == int(case["source_value"])


def test_mops_period_fixture_matches_repository_observations() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    observations = json.loads(OBSERVATIONS_PATH.read_text(encoding="utf-8"))
    fixture_rule = {
        case["source_value"]: case["report_period"] for case in fixture["cases"]
    }

    assert fixture_rule == observations["period_rule"]
    assert {
        (case["facts"]["tifrs-notes:Quarter"], case["derived"]["report_period"])
        for case in observations["cases"]
    } == set(fixture_rule.items())


@pytest.mark.parametrize("source_value", ["FY", "0", "Q5", "annual", ""])
def test_mops_source_period_rejects_unverified_aliases(source_value: str) -> None:
    with pytest.raises(ValueError, match="MOPS"):
        normalize_mops_report_period(source_value)


def test_step6_documents_period_semantics_and_scope() -> None:
    decision = DECISION_PATH.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE_PATH.read_text(encoding="utf-8")

    assert "Q1 / Q2 / Q3 / FY" in decision
    assert "FY != Q4" in decision
    assert "MOPS Q4 → FY" in decision
    assert "來源專用" in decision
    assert "不建立 production Schema" in acceptance
