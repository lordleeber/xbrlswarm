"""Step-30 regression tests against the fixed MOPS source corpus."""

import dataclasses
import gzip
import json
from pathlib import Path

import pytest

from xbrlswarm.discovery.cases import DISCOVERY_CASES
from xbrlswarm.discovery.mops import build_mops_xbrl_capture, verify_mops_capture_set
from xbrlswarm.mops_parser import ParsedMopsReport, parse_mops_report


DISCOVERY = Path("tests/fixtures/discovery/mops")
FIXTURES = Path("tests/fixtures/mops")


def test_all_twelve_verified_captures_parse_only_matrix_approved_fields() -> None:
    allowed = {
        "stock_id",
        "company_name",
        "fiscal_year",
        "report_period",
        "report_scope",
        "source_locator",
    }
    captures = verify_mops_capture_set(DISCOVERY)
    assert len(captures) == 12
    assert set(ParsedMopsReport.__dataclass_fields__) == allowed
    for capture in captures:
        metadata = json.loads(capture.metadata_path.read_text(encoding="utf-8"))
        parsed = parse_mops_report(
            capture.case,
            gzip.decompress(capture.body_path.read_bytes()),
            source_url=metadata["request"]["url"],
        )
        assert set(dataclasses.asdict(parsed)) == allowed
        assert parsed.stock_id == capture.case.stock_id
        assert parsed.fiscal_year == capture.case.fiscal_year
        assert parsed.report_period is capture.case.report_period
        assert parsed.report_scope == "consolidated"
        assert parsed.company_name
        assert parsed.source_locator == build_mops_xbrl_capture(capture.case).url


def test_step29_four_period_manifest_points_to_parseable_source_bytes() -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["consolidated"]:
        case = next(
            case for case in DISCOVERY_CASES
            if case.stock_id == item["stock_id"] and case.report_period.value == item["period"]
        )
        raw = gzip.decompress(Path(item["body"]).read_bytes())
        parsed = parse_mops_report(
            case, raw, source_url=build_mops_xbrl_capture(case).url
        )
        assert parsed.report_period.value == item["period"]


@pytest.mark.parametrize("kind", [
    "amendment_listing",
    "amendment_detail",
    "individual_listing",
    "individual_detail",
    "missing_result",
    "unexpected_layout",
    "amendment_attachment",
    "individual_attachment",
])
def test_non_xbrl_step29_responses_are_rejected(kind: str) -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    entry = next(item for item in manifest["raw_cases"] if item["kind"] == kind)
    raw = gzip.decompress((FIXTURES / entry["body"]).read_bytes())
    case = next(case for case in DISCOVERY_CASES if case.key == "2330-2024-Q1")
    with pytest.raises(ValueError):
        parse_mops_report(case, raw, source_url=build_mops_xbrl_capture(case).url)


def test_unverified_source_locator_and_scope_are_rejected() -> None:
    capture = verify_mops_capture_set(DISCOVERY)[0]
    body = gzip.decompress(capture.body_path.read_bytes())
    url = build_mops_xbrl_capture(capture.case).url
    with pytest.raises(ValueError, match="source_url"):
        parse_mops_report(capture.case, body, source_url=url.replace("report_id=C", "report_id=A"))

    changed_scope = body.replace(b"Consolidated report", b"Individual report")
    with pytest.raises(ValueError, match="ReportCategory"):
        parse_mops_report(capture.case, changed_scope, source_url=url)

    changed_type = body.replace(b"Financial report (general)", b"Correction report")
    with pytest.raises(ValueError, match="ReportType"):
        parse_mops_report(capture.case, changed_type, source_url=url)


def test_conflicting_source_facts_are_rejected() -> None:
    capture = verify_mops_capture_set(DISCOVERY)[0]
    body = gzip.decompress(capture.body_path.read_bytes())
    original_fact = (
        b'<ix:nonNumeric name="tifrs-notes:CompanyID" '
        b'contextRef="From20240101To20240331">2330</ix:nonNumeric>'
    )
    assert original_fact in body
    changed = body.replace(original_fact, original_fact.replace(b">2330<", b">6147<"), 1)
    with pytest.raises(ValueError, match="CompanyID"):
        parse_mops_report(
            capture.case, changed, source_url=build_mops_xbrl_capture(capture.case).url
        )
