"""Offline regressions for the fixed Step-41 Goodinfo pilot."""

import json
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit

from xbrlswarm.goodinfo_pilot import PILOT_CASES, run_goodinfo_pilot
from xbrlswarm.goodinfo_operations import GoodinfoOperationalClient


NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)


class Response:
    status = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __init__(self, url, body):
        self.url, self.body = url, body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self):
        return self.body

    def geturl(self):
        return self.url


def _list_page(stock, year):
    subject = f"公告本公司{year}年第1季合併財務報告"
    detail_url = "/tw/StockAnnounceDetail.asp?" + urlencode({
        "STOCK_ID": stock, "CLAIM_TIME": f"{year}/05/10 14:48:53", "SUBJECT": subject,
    })
    return (f'<html><title>公告一覽</title><body><a href="{detail_url.replace("&", "&amp;")}">'
            f'{subject}</a></body></html>').encode()


def _detail_page(stock, year):
    subject = f"公告本公司{year}年第1季合併財務報告"
    return (f"<html><head><title>{stock} 測試公司 公告訊息</title></head><body>"
            f"發言日期 {year}/05/10 發言時間 14:48:53 "
            f"主旨 {subject} 說 明 "
            f"1.財務報告報導期間起訖日期:{year}/01/01~{year}/03/31"
            "</body></html>").encode()


def test_fixed_cases_include_required_stocks_and_older_years():
    assert [case.key for case in PILOT_CASES] == [
        "4542-2024-Q1", "6147-2024-Q1", "2330-2024-Q1",
        "6147-2022-Q1", "2330-2020-Q1",
    ]
    assert all((case.start_date, case.end_date) ==
               (date(case.fiscal_year, 4, 1), date(case.fiscal_year, 6, 30))
               for case in PILOT_CASES)


def test_pilot_captures_and_parses_fixed_cases_without_evidence(tmp_path):
    now = [1000.0]
    requested = []

    def sleep(seconds):
        now[0] += seconds

    def opener(request, **_):
        url = request.full_url
        requested.append((url, now[0]))
        params = parse_qs(urlsplit(url).query)
        stock = params["STOCK_ID"][0]
        year = int(params.get("START_DT", params.get("CLAIM_TIME"))[0][:4])
        body = _detail_page(stock, year) if "Detail.asp" in url else _list_page(stock, year)
        return Response(url, body)

    client = GoodinfoOperationalClient(
        tmp_path, opener=opener, clock=lambda: now[0], sleeper=sleep,
        random_value=lambda: 0, retrieval_clock=lambda: NOW,
    )
    report = run_goodinfo_pilot(tmp_path, client=client)
    assert report["query_window_kind"] == "exploratory_not_legal_deadline"
    assert report["summary"] == {
        "cases": 5, "lists_captured": 5, "access_blocked": 0, "not_captured": 0,
        "details_parsed": 5, "matching_period_details": 5,
    }
    assert report["capture_mode"] == "network"
    assert all(row["capture_method"] == "network" for row in report["results"])
    assert report["results"][0]["detail_results"][0]["claim_time"] == "2024-05-10 14:48:53"
    assert all(row["matching_candidate_count"] == 1 for row in report["results"])
    assert all(row["detail_results"][0]["period_matches_case"] is True
               for row in report["results"])
    assert [time for _, time in requested] == [1000 + 3 * i for i in range(10)]
    assert not list(tmp_path.rglob("*.sqlite"))
    assert not list(tmp_path.rglob("*evidence*"))

    again = run_goodinfo_pilot(tmp_path, client=client)
    assert again == report
    assert len(requested) == 10


def test_pilot_records_access_block_and_does_not_infer_no_candidates(tmp_path):
    def opener(request, **_):
        raise HTTPError(request.full_url, 403, "Forbidden", {}, None)

    client = GoodinfoOperationalClient(tmp_path, opener=opener,
        clock=lambda: 1000.0, sleeper=lambda _: None,
        random_value=lambda: 0, retrieval_clock=lambda: NOW)
    report = run_goodinfo_pilot(tmp_path, client=client, cases=PILOT_CASES[:1])
    row = report["results"][0]
    assert row["status"] == "access_blocked"
    assert row["candidate_count"] is None
    assert row["matching_candidate_count"] is None
    assert row["error"] == "HTTP 403"
    assert report["summary"]["lists_captured"] == 0
    assert not list(tmp_path.rglob("*.html"))


def test_pilot_limits_detail_fetches_and_reports_truncation(tmp_path):
    calls = []

    def opener(request, **_):
        url = request.full_url
        calls.append(url)
        if "Detail.asp" in url:
            return Response(url, _detail_page("4542", 2024))
        original = _list_page("4542", 2024).decode()
        second = _list_page("4542", 2024).decode().replace("14%3A48%3A53", "14%3A49%3A53")
        # Use two distinct links from the same stock and query range.
        extra = second.split("<a href=", 1)[1].split("</a>", 1)[0]
        return Response(url, original.replace("</body>", f"<a href={extra}</a></body>" ).encode())

    client = GoodinfoOperationalClient(tmp_path, opener=opener,
        clock=lambda: 1000.0, sleeper=lambda _: None,
        random_value=lambda: 0, retrieval_clock=lambda: NOW)
    report = run_goodinfo_pilot(tmp_path, client=client,
                                cases=PILOT_CASES[:1], max_details_per_case=1)
    row = report["results"][0]
    assert row["matching_candidate_count"] == 2
    assert row["detail_limit_reached"] is True
    assert len(row["detail_results"]) == 1
    assert len(calls) == 2


def test_committed_live_report_preserves_blocked_cases_as_unknown():
    report = json.loads(Path("discovery/goodinfo_pilot_2026-09-24.json").read_text())
    assert report["pilot_cases"] == [case.key for case in PILOT_CASES]
    assert report["summary"] == {
        "cases": 5, "lists_captured": 0, "access_blocked": 5,
        "details_parsed": 0, "matching_period_details": 0,
    }
    assert all(row["status"] == "access_blocked" and row["error"] == "HTTP 403"
               and row["candidate_count"] is None and row["matching_candidate_count"] is None
               and row["list_raw_payload_hash"] is None and row["detail_results"] == []
               for row in report["results"])


def test_offline_pilot_never_contacts_goodinfo_and_marks_missing_captures(tmp_path):
    def opener(request, **_):
        raise AssertionError("offline pilot must not contact Goodinfo")

    def sleeper(_):
        raise AssertionError("offline pilot must not wait for a request slot")

    client = GoodinfoOperationalClient(tmp_path, opener=opener, clock=lambda: 1000.0,
        sleeper=sleeper, random_value=lambda: 0, retrieval_clock=lambda: NOW)
    report = run_goodinfo_pilot(tmp_path, client=client, offline=True)
    assert report["capture_mode"] == "offline_replay"
    assert [row["status"] for row in report["results"]] == ["not_captured"] * 5
    assert report["summary"]["not_captured"] == 5
    assert report["summary"]["lists_captured"] == 0
    assert all(row["candidate_count"] is None for row in report["results"])
    assert not (tmp_path / ".goodinfo-request-state.json").exists()
