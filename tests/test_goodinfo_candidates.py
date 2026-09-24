"""Step-36 candidate extraction from synthetic Goodinfo-shaped list HTML."""

import json
import hashlib
from dataclasses import fields
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import pytest

from xbrlswarm.domain import ReportPeriod
from xbrlswarm.goodinfo_candidates import (
    parse_captured_goodinfo_candidates,
    parse_goodinfo_candidates,
)
from xbrlswarm.goodinfo_list import AnnouncementListQuery, capture_announcement_list


QUERY = AnnouncementListQuery("6152", date(2024, 4, 1), date(2024, 5, 15))


def _detail(stock: str, time: str, subject: str, path: str = "/tw/StockAnnounceDetail.asp") -> str:
    return f"{path}?{urlencode({'CLAIM_TIME': time, 'STOCK_ID': stock, 'SUBJECT': subject})}"


def _page(*links: tuple[str, str]) -> bytes:
    anchors = "".join(f'<p><a href="{href.replace("&", "&amp;")}">{title}</a></p>'
                      for href, title in links)
    return f"<html><title>公告一覽</title><body>{anchors}</body></html>".encode()


def test_extracts_period_and_scope_hints_without_accepting_evidence() -> None:
    q1 = _detail("6152", "2024/05/07 14:19:00", "本公司2024年第1季合併財務報告")
    individual = _detail("6152", "2024/05/08 14:20:00", "本公司2024年第一季個體財務報告")
    scheduled = _detail("6152", "2024/04/29 14:39:00", "第一季財務報告董事會預計召開日期")
    body = _page(
        (q1, "百一董事會決議通過2024年第1季 <b>合併</b>財務報告"),
        (individual, "2024年第一季個體財務報告"),
        (scheduled, "2024年第1季財務報告董事會預計召開日期"),
        (q1, "百一董事會決議通過2024年第1季合併財務報告"),
        (_detail("6152", "2024/05/09 10:00:00", "營收"), "2024年4月營收公告"),
    )
    candidates = parse_goodinfo_candidates(
        body, query=QUERY, final_url=QUERY.url,
        content_type="text/html; charset=utf-8",
    )
    assert len(candidates) == 3
    assert candidates[0].report_period_hints == (ReportPeriod.Q1,)
    assert candidates[0].report_scope_hints == ("合併",)
    assert candidates[0].scheduled_meeting is False
    assert candidates[0].list_url == QUERY.url
    assert candidates[0].list_raw_payload_hash == f"sha256:{hashlib.sha256(body).hexdigest()}"
    assert candidates[1].report_scope_hints == ("個體",)
    assert candidates[2].scheduled_meeting is True
    assert all({field.name for field in fields(item)} == {
        "display_title", "detail_url", "list_url", "list_raw_payload_hash",
        "report_period_hints",
        "report_scope_hints", "scheduled_meeting",
    } for item in candidates)


def test_annual_and_unknown_scope_remain_hints() -> None:
    query = AnnouncementListQuery("6152", date(2025, 1, 1), date(2025, 3, 31))
    url = _detail("6152", "2025/03/12 15:15:00", "本公司2024年度財務報告")
    candidates = parse_goodinfo_candidates(
        _page((url, "百一董事會決議通過2024年度財務報告")),
        query=query, final_url=query.url, content_type="text/html; charset=utf-8",
    )
    assert len(candidates) == 1
    assert candidates[0].report_period_hints == (ReportPeriod.FY,)
    assert candidates[0].report_scope_hints == ()


@pytest.mark.parametrize(("title", "period", "scope"), [
    ("2026年度第二季個別財務報告", ReportPeriod.Q2, ("個體",)),
    ("2026年上半年度財務報告", ReportPeriod.Q2, ()),
    ("董事會通過2025年個別財務報告", ReportPeriod.FY, ("個體",)),
    ("董事會通過2026年第2季個別財務報告", ReportPeriod.Q2, ("個體",)),
    ("2025年度個體財務報告", ReportPeriod.FY, ("個體",)),
])
def test_real_title_forms_normalize_period_and_individual_scope(
    title: str, period: ReportPeriod, scope: tuple[str, ...],
) -> None:
    query = AnnouncementListQuery("6152", date(2026, 8, 1), date(2026, 8, 31))
    detail = _detail("6152", "2026/08/07 14:46:08", title)
    candidates = parse_goodinfo_candidates(
        _page((detail, title)), query=query, final_url=query.url,
        content_type="text/html; charset=utf-8",
    )
    assert len(candidates) == 1
    assert candidates[0].report_period_hints == (period,)
    assert candidates[0].report_scope_hints == scope


def test_lower_half_year_is_not_mistaken_for_an_annual_report() -> None:
    query = AnnouncementListQuery("6152", date(2026, 8, 1), date(2026, 8, 31))
    title = "2026年下半年度財務報告"
    detail = _detail("6152", "2026/08/07 14:46:08", title)
    assert parse_goodinfo_candidates(
        _page((detail, title)), query=query, final_url=query.url,
        content_type="text/html; charset=utf-8",
    ) == ()


def test_big5_list_title_is_decoded_without_changing_raw_hash() -> None:
    detail = _detail("6152", "2024/05/07 14:19:00", "本公司第1季合併財務報告")
    body = f'<html><a href="{detail.replace("&", "&amp;")}">第1季合併財務報告</a></html>'.encode("big5")
    candidates = parse_goodinfo_candidates(
        body, query=QUERY, final_url=QUERY.url,
        content_type="text/html; charset=big5",
    )
    assert len(candidates) == 1
    assert candidates[0].list_raw_payload_hash == f"sha256:{hashlib.sha256(body).hexdigest()}"


def test_other_company_outside_range_and_external_links_are_not_candidates() -> None:
    subject = "本公司2024年第1季合併財務報告"
    links = [
        (_detail("2330", "2024/05/07 14:19:00", subject), subject),
        (_detail("6152", "2024/05/16 14:19:00", subject), subject),
        ("https://evil.test" + _detail("6152", "2024/05/07 14:19:00", subject), subject),
        (_detail("6152", "bad-time", subject), subject),
        (_detail("6152", "2024/05/07 14:19:00", ""), subject),
    ]
    assert parse_goodinfo_candidates(
        _page(*links), query=QUERY, final_url=QUERY.url,
        content_type="text/html; charset=utf-8",
    ) == ()


@pytest.mark.parametrize("parameter", ["STOCK_ID", "CLAIM_TIME", "SUBJECT"])
def test_candidate_rejects_blank_duplicate_detail_identity(parameter: str) -> None:
    title = "本公司2024年第1季合併財務報告"
    url = _detail("6152", "2024/05/07 14:19:00", title) + f"&{parameter}="
    assert parse_goodinfo_candidates(
        _page((url, title)), query=QUERY, final_url=QUERY.url,
        content_type="text/html; charset=utf-8",
    ) == ()


def test_capture_hash_must_match_before_parsing(tmp_path: Path) -> None:
    detail = _detail("6152", "2024/05/07 14:19:00", "本公司第1季合併財務報告")
    body = _page((detail, "本公司第1季合併財務報告"))

    class Response:
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __init__(self, url):
            self.url = url

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return body

        def geturl(self):
            return self.url

    capture = capture_announcement_list(
        QUERY, tmp_path, opener=lambda request, **_: Response(request.full_url),
        clock=lambda: datetime(2026, 9, 24, tzinfo=timezone.utc),
    )
    assert len(parse_captured_goodinfo_candidates(capture)) == 1
    capture.body_path.write_bytes(body + b" ")
    with pytest.raises(ValueError, match="provenance"):
        parse_captured_goodinfo_candidates(capture)


def test_capture_rejects_changed_query_metadata(tmp_path: Path) -> None:
    detail = _detail("6152", "2024/05/07 14:19:00", "本公司第1季合併財務報告")
    body = _page((detail, "本公司第1季合併財務報告"))

    class Response:
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __init__(self, url):
            self.url = url

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return body

        def geturl(self):
            return self.url

    capture = capture_announcement_list(
        QUERY, tmp_path, opener=lambda request, **_: Response(request.full_url),
        clock=lambda: datetime(2026, 9, 24, tzinfo=timezone.utc),
    )
    metadata = json.loads(capture.metadata_path.read_text())
    metadata["query"]["stock_id"] = "2330"
    capture.metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="provenance"):
        parse_captured_goodinfo_candidates(capture)


def test_contract_keeps_candidates_separate_from_evidence() -> None:
    contract = json.loads(Path("contracts/goodinfo-list-candidates.json").read_text())
    assert contract["candidate_only"] is True
    assert contract["writes_evidence"] is False
    assert contract["empty_result_means_absence"] is False
    assert contract["detail_verification_step"] == 37
