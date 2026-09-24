"""Step-34 query and raw capture regressions."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from threading import Event
from urllib.parse import parse_qs, urlsplit

import pytest

from xbrlswarm.goodinfo_list import AnnouncementListQuery, capture_announcement_list


NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
HTML = '<!doctype html><html><title>上市櫃公司股市公告資訊一覽</title></html>'.encode()


class Response:
    def __init__(self, url: str, body: bytes = HTML, status: int = 200, headers=None):
        self.url = url
        self.body = body
        self.status = status
        self.headers = headers or {"Content-Type": "text/html; charset=UTF-8"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self):
        return self.body

    def geturl(self):
        return self.url


def query() -> AnnouncementListQuery:
    return AnnouncementListQuery("0050", date(2024, 1, 2), date(2024, 12, 31))


def test_query_keeps_stock_id_and_explicit_historical_dates() -> None:
    value = query()
    parsed = urlsplit(value.url)
    assert (parsed.scheme, parsed.netloc, parsed.path) == (
        "https", "goodinfo.tw", "/tw/StockAnnounceList.asp"
    )
    assert parse_qs(parsed.query) == {
        "STOCK_ID": ["0050"],
        "START_DT": ["2024/01/02"],
        "END_DT": ["2024/12/31"],
    }


@pytest.mark.parametrize("stock_id", ["", "../2330", "2330?PAGE=2", " 2330", "中華"])
def test_query_rejects_unsafe_stock_id(stock_id: str) -> None:
    with pytest.raises(ValueError, match="stock_id"):
        AnnouncementListQuery(stock_id, date(2024, 1, 1), date(2024, 2, 1))


def test_query_rejects_reverse_or_implicit_dates() -> None:
    with pytest.raises(ValueError, match="start_date"):
        AnnouncementListQuery("2330", date(2024, 2, 1), date(2024, 1, 1))
    with pytest.raises(ValueError, match="dates"):
        AnnouncementListQuery("2330", datetime(2024, 1, 1), date(2024, 2, 1))


def test_capture_preserves_raw_html_and_query_provenance(tmp_path: Path) -> None:
    seen = []

    def opener(request, *, timeout):
        seen.append((request.full_url, timeout))
        return Response(request.full_url)

    capture = capture_announcement_list(query(), tmp_path, opener=opener, clock=lambda: NOW)
    assert seen == [(query().url, 30)]
    assert capture.body_path.read_bytes() == HTML
    assert capture.raw_payload_hash == f"sha256:{hashlib.sha256(HTML).hexdigest()}"
    metadata = json.loads(capture.metadata_path.read_text())
    assert metadata["query"] == {
        "stock_id": "0050", "start_date": "2024-01-02",
        "end_date": "2024-12-31", "url": query().url,
    }
    assert metadata["response"]["raw_payload_hash"] == capture.raw_payload_hash
    assert metadata["retrieved_at"] == "2026-09-24T12:00:00Z"
    with pytest.raises(FileExistsError):
        capture_announcement_list(query(), tmp_path, opener=opener, clock=lambda: NOW)
    assert len(seen) == 1


def test_concurrent_capture_cannot_mix_body_and_metadata(tmp_path: Path) -> None:
    first_started = Event()
    release_first = Event()
    second_opened = Event()
    first_body = HTML + b"<!-- first -->"

    def first_opener(request, *, timeout):
        first_started.set()
        assert release_first.wait(timeout=5)
        return Response(request.full_url, body=first_body)

    def second_opener(request, *, timeout):
        second_opened.set()
        return Response(request.full_url, body=HTML + b"<!-- second -->")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            capture_announcement_list, query(), tmp_path,
            opener=first_opener, clock=lambda: NOW,
        )
        try:
            assert first_started.wait(timeout=5)
            second = pool.submit(
                capture_announcement_list, query(), tmp_path,
                opener=second_opener, clock=lambda: NOW,
            )
            with pytest.raises(FileExistsError):
                second.result(timeout=5)
        finally:
            release_first.set()
        capture = first.result(timeout=5)

    assert not second_opened.is_set()
    assert capture.body_path.read_bytes() == first_body
    metadata = json.loads(capture.metadata_path.read_text())
    assert metadata["response"]["raw_payload_hash"] == (
        f"sha256:{hashlib.sha256(first_body).hexdigest()}"
    )
    assert not list(tmp_path.rglob("*.capture.lock"))


def test_same_query_may_redirect_to_tw2_and_add_page_parameter(tmp_path: Path) -> None:
    final_url = query().url.replace("/tw/", "/tw2/") + "&PAGE=1"
    capture = capture_announcement_list(
        query(), tmp_path,
        opener=lambda request, **_: Response(final_url),
        clock=lambda: NOW,
    )
    metadata = json.loads(capture.metadata_path.read_text())
    assert metadata["response"]["final_url"] == final_url


def test_capture_accepts_big5_announcement_title(tmp_path: Path) -> None:
    body = "<html><title>公告資訊一覽</title></html>".encode("big5")
    capture = capture_announcement_list(
        query(), tmp_path,
        opener=lambda request, **_: Response(
            request.full_url, body=body,
            headers={"Content-Type": "text/html; charset=big5"},
        ),
        clock=lambda: NOW,
    )
    assert capture.body_path.read_bytes() == body


@pytest.mark.parametrize("response, message", [
    (lambda url: Response(url, status=403), "HTTP 403"),
    (lambda url: Response(url, headers={"Content-Type": "text/html", "cf-mitigated": "challenge"}), "challenge"),
    (lambda url: Response(url, body=b"<html>Just a moment...</html>"), "challenge"),
    (lambda url: Response(url, body="<html>初始化中</html>".encode()), "challenge"),
    (lambda url: Response(url.replace("STOCK_ID=0050", "STOCK_ID=2330")), "redirected"),
    (lambda url: Response(url, body=b"{not html}", headers={"Content-Type": "application/json"}), "HTML"),
    (lambda url: Response(url, body=b"<html>unrelated page</html>"), "announcement list"),
])
def test_rejected_response_does_not_create_list_files(tmp_path: Path, response, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        capture_announcement_list(query(), tmp_path, opener=lambda request, **_: response(request.full_url))
    assert not [path for path in tmp_path.rglob("*") if path.is_file()]
