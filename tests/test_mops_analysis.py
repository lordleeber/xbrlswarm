from __future__ import annotations

import json
from pathlib import Path

import pytest

from xbrlswarm.discovery.mops_analysis import (
    analyze_mops_capture_set,
    extract_mops_field_observation,
    render_mops_field_observations,
)
from xbrlswarm.discovery.models import DiscoveryCase, ReportPeriod


FIXTURE_ROOT = Path("tests/fixtures/discovery/mops")


def _ixbrl(
    *,
    stock_id: str = "2330",
    company_name: str = "台灣積體電路製造股份有限公司",
    year: str = "2024",
    quarter: str = "1",
    category: str = "Consolidated report",
) -> bytes:
    facts = {
        "CompanyID": stock_id,
        "CompanyChineseName": company_name,
        "Year": year,
        "Quarter": quarter,
        "ReportType": "Financial report (general)",
        "ReportCategory": category,
    }
    body = "".join(
        f'<ix:nonNumeric name="tifrs-notes:{name}" contextRef="c1">{value}</ix:nonNumeric>'
        for name, value in facts.items()
    )
    return (
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">'
        f"<body>{body}</body></html>"
    ).encode()


def test_repository_captures_produce_twelve_evidence_backed_observations() -> None:
    observations = analyze_mops_capture_set(FIXTURE_ROOT)

    assert len(observations) == 12
    assert {(item.stock_id, item.report_period.value) for item in observations} == {
        (stock_id, period)
        for stock_id in ("2330", "6147", "4542")
        for period in ("Q1", "Q2", "Q3", "FY")
    }
    assert {item.fiscal_year for item in observations} == {2024}
    assert {item.report_scope for item in observations} == {"consolidated"}
    assert {item.source_quarter for item in observations} == {1, 2, 3, 4}
    assert {item.company_name for item in observations if item.stock_id == "2330"} == {
        "台灣積體電路製造股份有限公司"
    }


def test_quarter_four_is_deterministically_mapped_to_fy() -> None:
    case = DiscoveryCase("2330", "台積電", 2024, ReportPeriod.FY)
    observation = extract_mops_field_observation(
        case,
        _ixbrl(quarter="4"),
        source_url="https://mops.example/download?season=4",
        sha256="a" * 64,
    )

    assert observation.source_quarter == 4
    assert observation.report_period is ReportPeriod.FY


def test_analysis_rejects_fact_that_disagrees_with_capture_case() -> None:
    case = DiscoveryCase("2330", "台積電", 2024, ReportPeriod.Q1)

    with pytest.raises(ValueError, match="CompanyID"):
        extract_mops_field_observation(
            case,
            _ixbrl(stock_id="6147"),
            source_url="https://mops.example/download?season=1",
            sha256="a" * 64,
        )


def test_analysis_rejects_missing_or_ambiguous_required_fact() -> None:
    case = DiscoveryCase("2330", "台積電", 2024, ReportPeriod.Q1)
    missing = _ixbrl().replace(
        b'<ix:nonNumeric name="tifrs-notes:Year" contextRef="c1">2024</ix:nonNumeric>',
        b"",
    )
    duplicate = _ixbrl().replace(
        b"</body>",
        b'<ix:nonNumeric name="tifrs-notes:Year" contextRef="c2">2023</ix:nonNumeric></body>',
    )

    with pytest.raises(ValueError, match="Year"):
        extract_mops_field_observation(
            case,
            missing,
            source_url="https://mops.example/download",
            sha256="a" * 64,
        )
    with pytest.raises(ValueError, match="Year"):
        extract_mops_field_observation(
            case,
            duplicate,
            source_url="https://mops.example/download",
            sha256="a" * 64,
        )


def test_repository_observation_artifact_is_deterministic() -> None:
    rendered = render_mops_field_observations(analyze_mops_capture_set(FIXTURE_ROOT))

    assert rendered == Path("discovery/mops_field_observations.json").read_text(encoding="utf-8")
    document = json.loads(rendered)
    assert document["capture_count"] == 12
    assert document["coverage"]["tifrs-notes:CompanyID"] == "12/12"
    assert document["coverage"]["tifrs-notes:ReportCategory"] == "12/12"
    assert document["period_rule"] == {"1": "Q1", "2": "Q2", "3": "Q3", "4": "FY"}
    assert document["semantic_review"]["distinct_fact_name_count"] == 494
    assert document["semantic_review"]["candidate_fact_names"] == [
        "tifrs-notes:ApplicationOfNewlyIssuedOrAmendedStandardsAndInterpretations",
        "tifrs-notes:DateAndProceduresOfAuthorisationForIssueOfFinancialStatements",
        "tifrs-notes:ReportType",
    ]
    assert document["not_observed"] == [
        "filing_identifier",
        "filing_date",
        "filing_time",
        "xbrl_confirmed_at",
        "filing_kind",
    ]
