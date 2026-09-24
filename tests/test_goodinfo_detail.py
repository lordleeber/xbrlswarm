"""Step-37 Goodinfo detail extraction and raw capture regressions."""

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import pytest

from xbrlswarm.domain import ReportPeriod
from xbrlswarm.goodinfo_candidates import GoodinfoListCandidate
from xbrlswarm.goodinfo_detail import (
    capture_goodinfo_detail,
    parse_captured_goodinfo_detail,
    parse_goodinfo_detail,
)


def _candidate(stock: str = "3117", time: str = "2026/08/07 17:06:00") -> GoodinfoListCandidate:
    subject = "公告本公司董事會通過115年第2季合併財務報告"
    url = "https://goodinfo.tw/tw/StockAnnounceDetail.asp?" + urlencode({
        "CLAIM_TIME": time, "STOCK_ID": stock, "SUBJECT": subject,
    })
    return GoodinfoListCandidate(
        "年程董事會通過2026年第2季合併財務報告", url,
        "https://goodinfo.tw/tw/StockAnnounceList.asp", "sha256:list",
        (ReportPeriod.Q2,), ("合併",), False,
    )


def _page(*, stock: str = "3117", subject: str = "公告本公司董事會通過2026年第2季合併財務報告",
          date_time: str = "2026/08/07 17:06:00", explanation: str | None = None) -> bytes:
    if explanation is None:
        explanation = (
            "1.財務報告提報董事會或經董事會決議日期:2026/08/07<br>"
            "2.審計委員會通過財務報告日期:2026/08/07<br>"
            "3.財務報告報導期間起訖日期(XXX/XX/XX~XXX/XX/XX):2026/01/01~2026/06/30"
        )
    day, time = date_time.split()
    return (
        f"<html><head><title>{stock} 年程 公告訊息 - Goodinfo</title></head>"
        f"<body><table><tr><td>發言日期</td><td>{day}</td><td>發言時間</td><td>{time}</td></tr>"
        f"<tr><td>主旨</td><td>{subject}</td></tr>"
        f"<tr><td>說　明</td><td>{explanation}</td></tr></table></body></html>"
    ).encode()


def _parse(body: bytes, candidate: GoodinfoListCandidate | None = None):
    candidate = candidate or _candidate()
    return parse_goodinfo_detail(
        body, candidate=candidate, final_url=candidate.detail_url,
        content_type="text/html; charset=utf-8",
    )


def test_extracts_visible_detail_fields_and_preserves_provenance() -> None:
    candidate = _candidate()
    detail = _parse(_page(), candidate)
    assert detail.stock_id == "3117"
    assert detail.claim_time == datetime(2026, 8, 7, 17, 6)
    assert detail.subject == "公告本公司董事會通過2026年第2季合併財務報告"
    assert (detail.period_start, detail.period_end) == (date(2026, 1, 1), date(2026, 6, 30))
    assert detail.board_date == date(2026, 8, 7)
    assert detail.audit_committee_date == date(2026, 8, 7)
    assert detail.detail_url == candidate.detail_url
    assert detail.final_url == candidate.detail_url
    assert detail.list_raw_payload_hash == candidate.list_raw_payload_hash
    assert detail.raw_payload_hash.startswith("sha256:")


def test_subject_identity_allows_observed_minguo_year_rendering() -> None:
    detail = _parse(_page(subject="公告本公司董事會通過 ２０２６年 第2季合併財務報告"))
    assert detail.subject == "公告本公司董事會通過 ２０２６年 第2季合併財務報告"


def test_same_stock_and_time_with_different_subject_is_rejected() -> None:
    with pytest.raises(ValueError, match="subject disagrees"):
        _parse(_page(subject="公告本公司董事會通過2026年第3季合併財務報告"))
    with pytest.raises(ValueError, match="subject disagrees"):
        _parse(_page(subject="公告本公司董事會通過2026年第2季個別財務報告"))


def test_alternate_labels_and_missing_fields_remain_unknown() -> None:
    explanation = (
        "1.提報董事會或經董事會決議日期:2026/08/07<br>"
        "2.審計委員會通過日期:2026/08/06<br>"
        "3.財務報告或年度自結財務資訊報導期間<br>"
        "起訖日期(XXX/XX/XX~XXX/XX/XX):2026/01/01～2026/06/30"
    )
    detail = _parse(_page(explanation=explanation))
    assert detail.audit_committee_date == date(2026, 8, 6)
    assert detail.period_end == date(2026, 6, 30)
    partial = _parse(_page(explanation="1.其他應敘明事項:無"))
    assert (partial.period_start, partial.period_end, partial.board_date,
            partial.audit_committee_date) == (None, None, None, None)


def test_big5_detail_keeps_hash_of_original_bytes() -> None:
    candidate = _candidate()
    body = _page().decode().encode("big5")
    detail = parse_goodinfo_detail(
        body, candidate=candidate, final_url=candidate.detail_url,
        content_type="text/html; charset=big5",
    )
    assert detail.period_end == date(2026, 6, 30)
    assert detail.raw_payload_hash == f"sha256:{hashlib.sha256(body).hexdigest()}"


@pytest.mark.parametrize("body,candidate", [
    (_page(stock="2330"), _candidate()),
    (_page(date_time="2026/08/08 17:06:00"), _candidate()),
    (_page(subject="公告營收"), _candidate()),
    (_page(explanation="1.報導期間起訖日期:2026/06/30~2026/01/01"), _candidate()),
])
def test_rejects_mismatched_or_invalid_announcements(body, candidate) -> None:
    with pytest.raises(ValueError):
        _parse(body, candidate)


def test_rejects_redirect_challenge_and_conflicting_dates() -> None:
    candidate = _candidate()
    with pytest.raises(ValueError, match="redirected"):
        parse_goodinfo_detail(_page(), candidate=candidate, final_url=_candidate("2330").detail_url,
                              content_type="text/html")
    with pytest.raises(ValueError, match="challenge"):
        _parse(_page() + b"<!-- cf-chl -->")
    with pytest.raises(ValueError, match="conflicting"):
        _parse(_page(explanation=(
            "1.提報董事會或經董事會決議日期:2026/08/07<br>"
            "2.提報董事會或經董事會決議日期:2026/08/08"
        )))


def test_same_identity_redirect_preserves_final_url() -> None:
    candidate = _candidate()
    final_url = candidate.detail_url.replace(
        "/tw/StockAnnounceDetail.asp", "/tw2/StockAnnounceDetail.asp", 1,
    )
    detail = parse_goodinfo_detail(
        _page(), candidate=candidate, final_url=final_url, content_type="text/html",
    )
    assert detail.detail_url == candidate.detail_url
    assert detail.final_url == final_url


def test_invalid_period_date_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid Goodinfo report period"):
        _parse(_page(explanation=(
            "3.財務報告報導期間起訖日期:2026/02/30~2026/06/30"
        )))


def test_capture_preserves_raw_bytes_and_rejects_tampering(tmp_path) -> None:
    candidate = _candidate()
    body = _page()

    class Response:
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return body

        def geturl(self):
            return candidate.detail_url

    capture = capture_goodinfo_detail(
        candidate, tmp_path, opener=lambda request, **_: Response(),
        clock=lambda: datetime(2026, 9, 24, tzinfo=timezone.utc),
    )
    assert capture.body_path.read_bytes() == body
    assert parse_captured_goodinfo_detail(capture).period_end == date(2026, 6, 30)
    with pytest.raises(FileExistsError):
        capture_goodinfo_detail(candidate, tmp_path, opener=lambda *a, **k: None)
    capture.body_path.write_bytes(body + b" ")
    with pytest.raises(ValueError, match="provenance"):
        parse_captured_goodinfo_detail(capture)
    capture.body_path.write_bytes(body)
    metadata = json.loads(capture.metadata_path.read_text())
    metadata["list_raw_payload_hash"] = "sha256:changed"
    capture.metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="provenance"):
        parse_captured_goodinfo_detail(capture)


def test_rejected_capture_does_not_create_raw_files(tmp_path) -> None:
    candidate = _candidate()

    class Response:
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8", "cf-mitigated": "challenge"}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return b"<html>cf-chl</html>"

        def geturl(self):
            return candidate.detail_url

    with pytest.raises(ValueError, match="challenge"):
        capture_goodinfo_detail(candidate, tmp_path, opener=lambda request, **_: Response())
    assert list(tmp_path.rglob("*.html")) == []
    assert list(tmp_path.rglob("*.json")) == []


def test_subject_mismatch_does_not_create_capture(tmp_path) -> None:
    candidate = _candidate()

    class Response:
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return _page(subject="公告本公司董事會通過2026年第3季合併財務報告")

        def geturl(self):
            return candidate.detail_url

    with pytest.raises(ValueError, match="subject disagrees"):
        capture_goodinfo_detail(candidate, tmp_path, opener=lambda request, **_: Response())
    assert list(tmp_path.rglob("*.html")) == []
    assert list(tmp_path.rglob("*.json")) == []


def test_contract_keeps_detail_parsing_separate_from_evidence() -> None:
    contract = json.loads(Path("contracts/goodinfo-detail.json").read_text())
    assert contract["required_visible_fields"] == ["stock_id", "claim_time", "subject"]
    assert "final_url" in contract["provenance"]
    assert "ROC year to Gregorian year" in contract["subject_identity_normalization"]
    assert contract["writes_evidence"] is False
    assert contract["writes_task"] is False
    assert contract["announcement_evidence_step"] == 38
