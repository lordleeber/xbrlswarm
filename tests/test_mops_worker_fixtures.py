"""Pin Step-29 source responses before implementing the MOPS worker parser."""

import gzip
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from xbrlswarm.discovery.mops import verify_mops_capture_set
from xbrlswarm.discovery.mops_analysis import analyze_mops_capture_set


ROOT = Path("tests/fixtures/mops")
DISCOVERY = Path("tests/fixtures/discovery/mops")


def _manifest() -> dict:
    return json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))


def test_four_periods_reuse_verified_raw_consolidated_captures() -> None:
    manifest = _manifest()
    cases = manifest["consolidated"]
    assert [case["period"] for case in cases] == ["Q1", "Q2", "Q3", "FY"]
    verified = {capture.case.key: capture for capture in verify_mops_capture_set(DISCOVERY)}
    observed = {item.case.key: item for item in analyze_mops_capture_set(DISCOVERY)}
    for case in cases:
        assert case["stock_id"] == "2330"
        assert case["fiscal_year"] == 2024
        assert case["report_scope"] == "consolidated"
        capture = verified[f"2330-2024-{case['period']}"]
        assert case["body"] == str(capture.body_path)
        assert case["headers"] == str(capture.headers_path)
        assert case["metadata"] == str(capture.metadata_path)
        assert case["sha256"] == capture.sha256
        assert observed[capture.case.key].report_period.value == case["period"]


def test_live_mops_response_triplets_preserve_bytes_headers_and_request() -> None:
    cases = _manifest()["raw_cases"]
    assert [case["kind"] for case in cases] == [
        "amendment_listing",
        "individual_listing",
        "missing_result",
        "unexpected_layout",
        "amendment_detail",
        "amendment_attachment",
        "individual_detail",
        "individual_attachment",
    ]
    for case in cases:
        body_path = ROOT / case["body"]
        metadata = json.loads((ROOT / case["metadata"]).read_text(encoding="utf-8"))
        headers = json.loads((ROOT / case["headers"]).read_text(encoding="utf-8"))
        raw = gzip.decompress(body_path.read_bytes())
        assert case["sha256"] == metadata["response"]["sha256"]
        assert hashlib.sha256(raw).hexdigest() == case["sha256"]
        assert len(raw) == metadata["response"]["size_bytes"]
        assert metadata["response"]["status"] == 200
        assert metadata["response"]["final_url"] == metadata["request"]["url"]
        assert metadata["response"]["body_file"] == case["body"]
        assert metadata["response"]["headers_file"] == case["headers"]
        assert metadata["response"]["content_encoding"] == "gzip"
        assert urlparse(metadata["request"]["url"]).hostname == "mopsov.twse.com.tw"
        assert metadata["request"]["method"] in {"GET", "POST"}
        assert isinstance(headers, list) and headers
        assert all("name" in item and "value" in item for item in headers)


def test_correction_and_individual_listings_are_observed_source_text() -> None:
    cases = {case["kind"]: case for case in _manifest()["raw_cases"]}
    amendment = gzip.decompress((ROOT / cases["amendment_listing"]["body"]).read_bytes())
    individual = gzip.decompress((ROOT / cases["individual_listing"]["body"]).read_bytes())
    assert "1314" in amendment.decode("utf-8")
    assert "更正民國113年第一季合併財務報告第29、60頁" in amendment.decode("utf-8")
    assert "1216" in individual.decode("utf-8")
    assert "IFRSs個體財報" in individual.decode("utf-8")
    assert "更正本公司113年度個體財務報表及附註" in individual.decode("utf-8")


def test_correction_details_link_to_captured_pdf_attachments() -> None:
    cases = {case["kind"]: case for case in _manifest()["raw_cases"]}
    for kind, company in (("amendment", "1314"), ("individual", "1216")):
        detail = gzip.decompress((ROOT / cases[f"{kind}_detail"]["body"]).read_bytes())
        attachment = gzip.decompress(
            (ROOT / cases[f"{kind}_attachment"]["body"]).read_bytes()
        )
        attachment_meta = json.loads(
            (ROOT / cases[f"{kind}_attachment"]["metadata"]).read_text(encoding="utf-8")
        )
        assert company in detail.decode("utf-8")
        assert attachment_meta["request"]["url"].rsplit("/", 1)[-1] in detail.decode("utf-8")
        assert attachment.startswith(b"%PDF-")


def test_missing_and_unexpected_layout_are_not_treated_as_xbrl() -> None:
    cases = {case["kind"]: case for case in _manifest()["raw_cases"]}
    missing = gzip.decompress((ROOT / cases["missing_result"]["body"]).read_bytes())
    unexpected = gzip.decompress((ROOT / cases["unexpected_layout"]["body"]).read_bytes())
    assert "查無資料" in missing.decode("utf-8")
    assert "下載檔名或路徑不正確" in unexpected.decode("big5")
    for raw in (missing, unexpected):
        assert b"ix:nonNumeric" not in raw
        assert b"ix:nonFraction" not in raw


def test_fixture_limitations_do_not_claim_individual_xbrl_or_absence() -> None:
    manifest = _manifest()
    assert manifest["individual_xbrl_document"] == "not_captured"
    assert manifest["missing_result_meaning"] == "query_returned_no_rows_only"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "個體" in readme and "更正" in readme
