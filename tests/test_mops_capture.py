from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from xbrlswarm.discovery.cases import DISCOVERY_CASES
from xbrlswarm.discovery.models import ReportPeriod
from xbrlswarm.discovery.mops import (
    build_mops_xbrl_capture,
    capture_mops_discovery_cases,
    verify_mops_capture_set,
)


def _content_disposition(url: str) -> str:
    query = parse_qs(urlparse(url).query)
    season = query["season"][0]
    return (
        'attachment; filename="'
        f'tifrs-fr1-m1-ci-cr-{query["co_id"][0]}-{query["year"][0]}Q{season}.html'
        '"'
    )


def _ixbrl_body(label: str = "fixture") -> bytes:
    return (
        '<!doctype html><html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">'
        f'<ix:nonNumeric name="x:{label}" contextRef="c1">{label}</ix:nonNumeric>'
        "</html>"
    ).encode()


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        url: str,
        *,
        content_disposition: str | None = None,
    ) -> None:
        self._body = body
        self._url = url
        self.status = 200
        headers = Message()
        headers["Content-Type"] = "application/octet-stream"
        headers["Content-Disposition"] = content_disposition or _content_disposition(url)
        headers["X-Test"] = "step-2"
        self.headers = headers

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


def test_mops_xbrl_requests_cover_all_fixed_cases() -> None:
    expected_season = {
        ReportPeriod.Q1: "1",
        ReportPeriod.Q2: "2",
        ReportPeriod.Q3: "3",
        ReportPeriod.FY: "4",
    }

    assert len(DISCOVERY_CASES) == 12
    for case in DISCOVERY_CASES:
        capture = build_mops_xbrl_capture(case)
        parsed = urlparse(capture.url)
        query = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert parsed.netloc == "mopsov.twse.com.tw"
        assert parsed.path == "/server-java/FileDownLoad"
        assert query == {
            "functionName": ["t164sb01"],
            "step": ["9"],
            "co_id": [case.stock_id],
            "year": ["2024"],
            "season": [expected_season[case.report_period]],
            "report_id": ["C"],
        }
        assert capture.name == "xbrl-consolidated"
        assert capture.extension == "bin"
        assert capture.method == "GET"


def test_capture_all_fixed_cases_and_verify_hashes(tmp_path: Path) -> None:
    seen_urls: list[str] = []

    def opener(request, timeout: float):
        seen_urls.append(request.full_url)
        return FakeResponse(_ixbrl_body(request.full_url), request.full_url)

    results = capture_mops_discovery_cases(
        tmp_path,
        opener=opener,
        now=lambda: datetime(2026, 9, 20, 6, 45, tzinfo=timezone.utc),
    )

    assert len(results) == 12
    assert len(seen_urls) == 12
    assert len(set(seen_urls)) == 12

    verified = verify_mops_capture_set(tmp_path)
    assert len(verified) == 12

    for item in verified:
        stored = item.body_path.read_bytes()
        body = gzip.decompress(stored)
        metadata = json.loads(item.metadata_path.read_text(encoding="utf-8"))
        assert item.body_path.name == "xbrl-consolidated.bin.gz"
        assert item.sha256 == hashlib.sha256(body).hexdigest()
        assert metadata["response"]["sha256"] == item.sha256
        assert metadata["response"]["size_bytes"] == len(body)
        assert metadata["response"]["stored_size_bytes"] == len(stored)
        assert metadata["response"]["content_encoding"] == "gzip"
        assert metadata["request"]["url"] == build_mops_xbrl_capture(item.case).url

    assert not list(tmp_path.rglob("*.capture.lock"))
    assert not list(tmp_path.rglob("xbrl-consolidated.bin"))


def test_verify_accepts_repository_mops_fixtures() -> None:
    verified = verify_mops_capture_set(Path("tests/fixtures/discovery/mops"))
    assert len(verified) == 12


def test_verify_rejects_tampered_body(tmp_path: Path) -> None:
    def opener(request, timeout: float):
        return FakeResponse(_ixbrl_body("original"), request.full_url)

    capture_mops_discovery_cases(tmp_path, opener=opener)
    target = tmp_path / "2330" / "2024" / "Q1" / "xbrl-consolidated.bin.gz"
    target.write_bytes(gzip.compress(b"tampered", mtime=0))

    with pytest.raises(ValueError, match="SHA-256"):
        verify_mops_capture_set(tmp_path)


def test_verify_requires_all_fixed_cases(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="2330-2024-Q1"):
        verify_mops_capture_set(tmp_path)


def test_verify_rejects_non_xbrl_success_page(tmp_path: Path) -> None:
    def opener(request, timeout: float):
        return FakeResponse(
            b"<html>FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED.</html>",
            request.full_url,
        )

    capture_mops_discovery_cases(tmp_path, opener=opener)

    with pytest.raises(ValueError, match="XBRL"):
        verify_mops_capture_set(tmp_path)


def test_verify_rejects_arbitrary_pk_prefixed_payload(tmp_path: Path) -> None:
    def opener(request, timeout: float):
        return FakeResponse(b"PK-this-is-not-a-zip-or-xbrl", request.full_url)

    capture_mops_discovery_cases(tmp_path, opener=opener)

    with pytest.raises(ValueError, match="XBRL"):
        verify_mops_capture_set(tmp_path)


def test_verify_rejects_response_for_wrong_case(tmp_path: Path) -> None:
    def opener(request, timeout: float):
        return FakeResponse(_ixbrl_body(request.full_url), request.full_url)

    capture_mops_discovery_cases(tmp_path, opener=opener)
    headers_path = (
        tmp_path / "6147" / "2024" / "Q1" / "xbrl-consolidated.headers.json"
    )
    headers = json.loads(headers_path.read_text(encoding="utf-8"))
    for item in headers:
        if item["name"].lower() == "content-disposition":
            item["value"] = (
                'attachment; filename="tifrs-fr1-m1-ci-cr-2330-2024Q1.html"'
            )
    headers_path.write_text(
        json.dumps(headers, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Content-Disposition"):
        verify_mops_capture_set(tmp_path)


def test_batch_capture_preflights_all_existing_targets(tmp_path: Path) -> None:
    conflict = (
        tmp_path / "2330" / "2024" / "Q2" / "xbrl-consolidated.bin.gz"
    )
    conflict.parent.mkdir(parents=True)
    conflict.write_bytes(b"existing")
    calls = 0

    def opener(request, timeout: float):
        nonlocal calls
        calls += 1
        return FakeResponse(_ixbrl_body(request.full_url), request.full_url)

    with pytest.raises(FileExistsError):
        capture_mops_discovery_cases(tmp_path, opener=opener)

    assert calls == 0
    assert not (
        tmp_path / "2330" / "2024" / "Q1" / "xbrl-consolidated.bin.gz"
    ).exists()
