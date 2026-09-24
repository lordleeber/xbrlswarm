"""Step-40 shared Goodinfo rate gate and cache regressions."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, datetime, timezone
from threading import Event
from urllib.parse import urlencode

import pytest

from xbrlswarm.domain import ReportPeriod
from xbrlswarm.goodinfo_candidates import GoodinfoListCandidate
from xbrlswarm.goodinfo_detail import parse_captured_goodinfo_detail
from xbrlswarm.goodinfo_list import AnnouncementListQuery
from xbrlswarm.goodinfo_list import main as list_main
from xbrlswarm.goodinfo_operations import GoodinfoOperationalClient, GoodinfoRequestPolicy


LIST_HTML = b"<html><title>StockAnnounceList</title></html>"
DETAIL_HTML = (
    "<html><head><title>3117 年程 公告訊息</title></head><body>"
    "發言日期 2026/08/07 發言時間 17:06:00 "
    "主旨 公告本公司董事會通過2026年第2季合併財務報告 "
    "說 明 1.財務報告報導期間起訖日期:2026/01/01~2026/06/30"
    "</body></html>"
).encode()
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


def query(day=1):
    return AnnouncementListQuery("3117", date(2026, 8, day), date(2026, 8, 31))


def candidate():
    subject = "公告本公司董事會通過115年第2季合併財務報告"
    url = "https://goodinfo.tw/tw/StockAnnounceDetail.asp?" + urlencode({
        "STOCK_ID": "3117", "CLAIM_TIME": "2026/08/07 17:06:00", "SUBJECT": subject,
    })
    return GoodinfoListCandidate(
        subject, url, query().url, "sha256:list", (ReportPeriod.Q2,), ("合併",), False,
    )


def test_reuses_valid_list_cache_without_request_or_wait(tmp_path):
    calls = []

    def opener(request, **_):
        calls.append(request.full_url)
        return Response(request.full_url, LIST_HTML)

    client = GoodinfoOperationalClient(tmp_path, opener=opener, sleeper=lambda _: pytest.fail("slept"),
                                       retrieval_clock=lambda: NOW)
    first = client.capture_list(query())
    second = client.capture_list(query())
    assert first == second
    assert calls == [query().url]


def test_list_cli_uses_guarded_cache(tmp_path, monkeypatch, capsys):
    import xbrlswarm.goodinfo_operations as operations

    calls = []
    real_client = operations.GoodinfoOperationalClient

    def client(root):
        def opener(request, **_):
            calls.append(request.full_url)
            return Response(request.full_url, LIST_HTML)

        return real_client(root, opener=opener, retrieval_clock=lambda: NOW)

    monkeypatch.setattr(operations, "GoodinfoOperationalClient", client)
    args = ["--stock-id", "3117", "--start-date", "2026-08-01",
            "--end-date", "2026-08-31", "--output-root", str(tmp_path)]
    assert list_main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert list_main(args) == 0
    assert json.loads(capsys.readouterr().out) == first
    assert calls == [query().url]


def test_shared_delay_and_jitter_cover_list_and_detail(tmp_path):
    now = [1000.0]
    calls, sleeps = [], []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    def opener(request, **_):
        calls.append((request.full_url, now[0]))
        body = DETAIL_HTML if "Detail.asp" in request.full_url else LIST_HTML
        return Response(request.full_url, body)

    client = GoodinfoOperationalClient(
        tmp_path, opener=opener, clock=lambda: now[0], sleeper=sleep,
        random_value=lambda: 0.5, retrieval_clock=lambda: NOW,
    )
    client.capture_list(query())
    detail = client.capture_detail(candidate())
    client.capture_list(query(2))
    assert parse_captured_goodinfo_detail(detail).period_end == date(2026, 6, 30)
    assert [at for _, at in calls] == [1000.0, 1004.0, 1008.0]
    assert sleeps == [4.0, 4.0]
    assert json.loads((tmp_path / ".goodinfo-request-state.json").read_text()) == {
        "next_allowed_at": 1012.0,
    }


def test_detail_cache_keeps_original_list_provenance(tmp_path):
    calls = []

    def opener(request, **_):
        calls.append(request.full_url)
        return Response(request.full_url, DETAIL_HTML)

    client = GoodinfoOperationalClient(tmp_path, opener=opener, retrieval_clock=lambda: NOW)
    first = client.capture_detail(candidate())
    another_list = replace(candidate(), list_url="https://goodinfo.tw/tw2/StockAnnounceList.asp",
                           list_raw_payload_hash="sha256:other")
    second = client.capture_detail(another_list)
    assert first == second
    assert len(calls) == 1
    assert parse_captured_goodinfo_detail(second).list_raw_payload_hash == "sha256:list"


def test_concurrent_same_range_uses_one_request(tmp_path):
    entered, release = Event(), Event()
    calls = []

    def opener(request, **_):
        calls.append(request.full_url)
        entered.set()
        assert release.wait(5)
        return Response(request.full_url, LIST_HTML)

    client = GoodinfoOperationalClient(tmp_path, opener=opener, retrieval_clock=lambda: NOW)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.capture_list, query())
        assert entered.wait(5)
        second = pool.submit(client.capture_list, query())
        release.set()
        assert first.result(timeout=5) == second.result(timeout=5)
    assert calls == [query().url]


def test_different_queries_serialize_across_clients(tmp_path):
    entered, release, second_entered = Event(), Event(), Event()

    def first_opener(request, **_):
        entered.set()
        assert release.wait(5)
        return Response(request.full_url, LIST_HTML)

    def second_opener(request, **_):
        second_entered.set()
        return Response(request.full_url, LIST_HTML)

    first_client = GoodinfoOperationalClient(tmp_path, opener=first_opener,
        policy=GoodinfoRequestPolicy(0.001, 0), retrieval_clock=lambda: NOW)
    second_client = GoodinfoOperationalClient(tmp_path, opener=second_opener,
        policy=GoodinfoRequestPolicy(0.001, 0), retrieval_clock=lambda: NOW)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_client.capture_list, query())
        try:
            assert entered.wait(5)
            second = pool.submit(second_client.capture_list, query(2))
            assert not second_entered.wait(0.05)
        finally:
            release.set()
        first.result(timeout=5)
        second.result(timeout=5)
    assert second_entered.is_set()


def test_rejected_request_consumes_cooldown_but_creates_no_cache(tmp_path):
    now = [1000.0]
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    def rejected(request, **_):
        return Response(request.full_url, b"<html>Just a moment...</html>")

    first = GoodinfoOperationalClient(tmp_path, opener=rejected, clock=lambda: now[0],
        sleeper=sleep, random_value=lambda: 0, retrieval_clock=lambda: NOW)
    with pytest.raises(ValueError, match="challenge"):
        first.capture_list(query())
    assert not list(tmp_path.rglob("*.html"))
    second = GoodinfoOperationalClient(tmp_path,
        opener=lambda request, **_: Response(request.full_url, LIST_HTML),
        clock=lambda: now[0], sleeper=sleep, random_value=lambda: 0,
        retrieval_clock=lambda: NOW)
    second.capture_list(query())
    assert sleeps == [3.0]


def test_incomplete_or_corrupt_cache_fails_without_refetch(tmp_path):
    client = GoodinfoOperationalClient(tmp_path,
        opener=lambda request, **_: Response(request.full_url, LIST_HTML), retrieval_clock=lambda: NOW)
    capture = client.capture_list(query())
    capture.body_path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="provenance"):
        GoodinfoOperationalClient(tmp_path, opener=lambda *_args, **_kwargs: pytest.fail("refetch"))\
            .capture_list(query())
    capture.metadata_path.unlink()
    with pytest.raises(ValueError, match="incomplete"):
        client.capture_list(query())


@pytest.mark.parametrize("delay,jitter", [(0, 0), (-1, 0), (1, -1)])
def test_policy_rejects_nonpositive_delay_or_negative_jitter(delay, jitter):
    with pytest.raises(ValueError):
        GoodinfoRequestPolicy(delay, jitter)
